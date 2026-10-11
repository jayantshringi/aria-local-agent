"""Device pairing engine for seamless mobile & cross-device enrollment."""

import io
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import aiosqlite
import qrcode
import qrcode.image.svg

from app.auth.security import generate_device_token, hash_token
from app.db import repository

# Human-friendly alphabet excluding ambiguous characters: 0, O, 1, I
PAIRING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_pairing_code() -> str:
    """Generate a readable, short-lived 8-character pairing code (e.g. ARIA-7K9P)."""
    random_part = "".join(secrets.choice(PAIRING_ALPHABET) for _ in range(4))
    return f"ARIA-{random_part}"


def generate_pairing_qr_svg(url_or_payload: str) -> str:
    """Generate a clean, standalone SVG QR code string without external cloud calls."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(url_or_payload)
    qr.make(fit=True)

    img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    stream = io.BytesIO()
    img.save(stream)
    return stream.getvalue().decode("utf-8")


async def create_pairing_session(
    conn: aiosqlite.Connection,
    created_by_device_id: str,
    ttl_seconds: int = 600,
) -> dict[str, Any]:
    """
    Create a new pairing code session with expiration timestamp.
    Defaults to 10-minute validity.
    """
    now = datetime.now(UTC)
    expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()

    # Retry loop in the astronomically unlikely event of code collision
    for _ in range(5):
        code = generate_pairing_code()
        existing = await repository.get_pairing_code(conn, code)
        if not existing:
            break
    else:
        # Fallback to random hex if collision occurred 5 times
        code = f"ARIA-{secrets.token_hex(3).upper()}"

    record = await repository.create_pairing_code(
        conn,
        code=code,
        created_by_device_id=created_by_device_id,
        expires_at=expires_at,
    )
    return {
        "id": record["id"],
        "code": record["code"],
        "expires_at": record["expires_at"],
        "ttl_seconds": ttl_seconds,
    }


async def claim_pairing_session(
    conn: aiosqlite.Connection,
    code: str,
    device_name: str = "Mobile Client",
) -> dict[str, Any] | None:
    """
    Claim an active pairing code and register the new device.
    Returns the newly registered device record and its raw device token.
    Returns None if the code is invalid, expired, or already claimed.
    """
    clean_code = code.strip().upper()
    record = await repository.get_pairing_code(conn, clean_code)
    if not record:
        return None

    if record.get("claimed_at") is not None:
        return None

    now_iso = datetime.now(UTC).isoformat()
    if record["expires_at"] <= now_iso:
        return None

    # Register new device
    raw_token = generate_device_token()
    token_hash = hash_token(raw_token)
    device = await repository.register_device(
        conn,
        name=device_name or "Mobile Client",
        token_hash=token_hash,
    )

    claimed = await repository.claim_pairing_code(
        conn,
        code=clean_code,
        claimed_by_device_id=device["id"],
    )
    if not claimed:
        return None

    return {
        "token": raw_token,
        "device": device,
    }
