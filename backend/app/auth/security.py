"""Authentication and device authorization utilities."""

import hashlib
import hmac
import os
import secrets
from typing import Any

import aiosqlite
from fastapi import Header, HTTPException, Query, status

from app.db import repository
from app.db.connection import get_database

# Iteration count for PBKDF2 password hashing
PBKDF2_ITERATIONS = 100_000
SALT_BYTES = 16


def hash_token(raw_token: str) -> str:
    """Compute deterministic SHA-256 hash of a device token for storage and lookup."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def generate_device_token() -> str:
    """Generate a high-entropy URL-safe random device token (32 bytes / 43+ chars)."""
    return secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with random salt."""
    salt = os.urandom(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}:{derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored salt:derived hash."""
    try:
        salt_hex, derived_hex = stored_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(derived_hex)
        computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return hmac.compare_digest(computed, expected)
    except Exception:
        return False


async def authenticate_or_init_master_password(
    conn: aiosqlite.Connection, password: str
) -> tuple[bool, bool]:
    """
    Authenticate against master password, or initialize it if this is the first setup.
    Returns (authenticated: bool, was_initialized: bool).
    """
    stored = await repository.get_setting(conn, "master_password_hash")
    if stored is None:
        # First-time initialization
        new_hash = hash_password(password)
        await repository.set_setting(conn, "master_password_hash", new_hash)
        return True, True

    return verify_password(password, stored), False


async def verify_device_token(conn: aiosqlite.Connection, raw_token: str) -> dict[str, Any] | None:
    """Validate a raw device token, returning the device record if valid and active."""
    if not raw_token:
        return None
    token_hash = hash_token(raw_token)
    device = await repository.get_device_by_token_hash(conn, token_hash)
    if device is not None:
        await repository.update_device_last_seen(conn, device["id"])
    return device


async def get_current_device(
    authorization: str | None = Header(None),
    x_device_token: str | None = Header(None),
    token: str | None = Query(None),
) -> dict[str, Any]:
    """
    FastAPI dependency for endpoint protection.
    Accepts token via Authorization Bearer, X-Device-Token header, or ?token query param.
    """
    extracted_token = None
    if authorization and authorization.startswith("Bearer "):
        extracted_token = authorization[7:].strip()
    elif x_device_token:
        extracted_token = x_device_token.strip()
    elif token:
        extracted_token = token.strip()

    if not extracted_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db = get_database()
    async with db.get_connection() as conn:
        device = await verify_device_token(conn, extracted_token)
        if not device:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked device token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return device
