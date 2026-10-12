"""Tests for scripts/backup.py encrypted backup and recovery utility."""

import sqlite3
from pathlib import Path

import pytest
from scripts.backup import (
    MAGIC_HEADER,
    create_backup,
    decrypt_payload,
    encrypt_payload,
    restore_backup,
    verify_backup,
)


def test_encrypt_decrypt_payload():
    """Test authenticated payload encryption and decryption."""
    data = b"Sensitive memory and session contents for Aria"
    pwd = "super-secure-master-password-123"

    encrypted = encrypt_payload(data, pwd)
    assert encrypted.startswith(MAGIC_HEADER)
    assert len(encrypted) > len(data)

    # Valid decryption
    decrypted = decrypt_payload(encrypted, pwd)
    assert decrypted == data

    # Wrong password raises ValueError
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_payload(encrypted, "wrong-password")

    # Tampered ciphertext raises ValueError
    tampered = bytearray(encrypted)
    tampered[-5] ^= 0xFF
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_payload(bytes(tampered), pwd)


def test_create_and_restore_backup(tmp_path: Path):
    """Test full directory backup and restoration pipeline."""
    # 1. Setup mock source data directory
    source_dir = tmp_path / "backup_src"
    source_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy database
    db_file = source_dir / "aria.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, note TEXT);")
    conn.execute("INSERT INTO test (note) VALUES ('secret project details');")
    conn.commit()
    conn.close()

    # Create persona and config files
    (source_dir / "persona.md").write_text("# My Personal Assistant", encoding="utf-8")
    (source_dir / "secret.key").write_text("0123456789abcdef", encoding="utf-8")

    # Create sandbox subfolder
    sandbox = source_dir / "sandbox"
    sandbox.mkdir()
    (sandbox / "sample.txt").write_text("Hello from sandbox", encoding="utf-8")

    # 2. Perform backup
    backup_file = tmp_path / "test_backup.aria-bak"
    pwd = "strong-owner-password"
    out = create_backup(source_dir, backup_file, pwd)
    assert out.exists()
    assert out.stat().st_size > 0

    # 3. Verify backup
    assert verify_backup(backup_file, pwd) is True
    with pytest.raises(ValueError):
        verify_backup(backup_file, "incorrect-pass")

    # 4. Restore into clean directory
    restore_dir = tmp_path / "restored_aria_data"
    restore_backup(backup_file, restore_dir, pwd)

    assert (restore_dir / "persona.md").read_text(encoding="utf-8") == "# My Personal Assistant"
    assert (restore_dir / "secret.key").read_text(encoding="utf-8") == "0123456789abcdef"
    assert (restore_dir / "sandbox" / "sample.txt").read_text(
        encoding="utf-8"
    ) == "Hello from sandbox"

    # Verify restored SQLite database contents
    res_conn = sqlite3.connect(str(restore_dir / "aria.db"))
    rows = res_conn.execute("SELECT note FROM test;").fetchall()
    res_conn.close()
    assert rows == [("secret project details",)]


def test_restore_overwrite_protection(tmp_path: Path):
    """Test safety check preventing accidental overwrite of existing target."""
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "persona.md").write_text("Original", encoding="utf-8")

    backup_file = tmp_path / "bak.aria-bak"
    create_backup(source_dir, backup_file, "pass123")

    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "existing.txt").write_text("Do not overwrite accidentally", encoding="utf-8")

    # Attempt restore without force/overwrite
    with pytest.raises(FileExistsError):
        restore_backup(backup_file, target_dir, "pass123", overwrite=False)

    # With overwrite=True
    restore_backup(backup_file, target_dir, "pass123", overwrite=True)
    assert (target_dir / "persona.md").exists()
