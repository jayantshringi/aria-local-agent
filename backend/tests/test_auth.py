"""Tests for authentication and device authorization security."""

import pytest

from app.auth.security import (
    authenticate_or_init_master_password,
    generate_device_token,
    hash_password,
    hash_token,
    verify_device_token,
    verify_password,
)
from app.db import repository
from app.db.connection import Database


def test_token_hashing_and_randomness():
    """Verify that device tokens are random and hashing is deterministic."""
    t1 = generate_device_token()
    t2 = generate_device_token()
    assert t1 != t2
    assert len(t1) >= 40

    h1 = hash_token(t1)
    h2 = hash_token(t1)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_password_hashing_verification():
    """Verify password hashing with salt and constant-time check."""
    pw = "SuperSecureLocalPassword123!"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


@pytest.mark.asyncio
async def test_master_password_init_and_verification(initialized_db: Database):
    """Test initial master password setup and subsequent login verification."""
    async with initialized_db.get_connection() as conn:
        # First-time initialization
        ok, was_init = await authenticate_or_init_master_password(conn, "InitialPassphrase")
        assert ok is True
        assert was_init is True

        # Second login with right password
        ok2, was_init2 = await authenticate_or_init_master_password(conn, "InitialPassphrase")
        assert ok2 is True
        assert was_init2 is False

        # Wrong password
        ok3, _ = await authenticate_or_init_master_password(conn, "IncorrectPassphrase")
        assert ok3 is False


@pytest.mark.asyncio
async def test_device_token_lifecycle(initialized_db: Database):
    """Test device registration, verification, and revocation."""
    async with initialized_db.get_connection() as conn:
        raw_token = generate_device_token()
        t_hash = hash_token(raw_token)
        device = await repository.register_device(conn, "Phone (Pixel 8)", t_hash)

        # Valid token verification
        verified = await verify_device_token(conn, raw_token)
        assert verified is not None
        assert verified["id"] == device["id"]

        # Revoke device
        await repository.revoke_device(conn, device["id"])

        # Verification after revocation must fail
        revoked_verified = await verify_device_token(conn, raw_token)
        assert revoked_verified is None
