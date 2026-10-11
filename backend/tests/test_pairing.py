"""Unit tests for Phase 3 device pairing engine, QR codes, and claim endpoints."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.auth.pairing import (
    claim_pairing_session,
    create_pairing_session,
    generate_pairing_code,
    generate_pairing_qr_svg,
)
from app.auth.security import generate_device_token, hash_token
from app.db import repository


@pytest.mark.asyncio
async def test_generate_pairing_code_format():
    """Verify pairing code format ARIA-XXXX with allowed alphabet."""
    code = generate_pairing_code()
    assert code.startswith("ARIA-")
    assert len(code) == 9
    suffix = code.split("-")[1]
    assert len(suffix) == 4
    for char in suffix:
        assert char in "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


@pytest.mark.asyncio
async def test_generate_pairing_qr_svg():
    """Verify standalone QR SVG generation without external calls."""
    svg = generate_pairing_qr_svg("/?pair=ARIA-84K2")
    assert "<svg" in svg
    assert "</svg>" in svg
    assert "viewBox" in svg


@pytest.mark.asyncio
async def test_pairing_session_lifecycle(initialized_db):
    """Test creating, fetching, and claiming a pairing session in SQLite."""
    async with initialized_db.get_connection() as conn:
        # Create initial host device
        host_token = generate_device_token()
        host = await repository.register_device(conn, "Host PC", hash_token(host_token))

        # Create pairing session
        session = await create_pairing_session(
            conn, created_by_device_id=host["id"], ttl_seconds=300
        )
        code = session["code"]
        assert code.startswith("ARIA-")
        assert session["ttl_seconds"] == 300

        # Claim pairing session
        claimed = await claim_pairing_session(conn, code=code, device_name="iPhone 15")
        assert claimed is not None
        assert "token" in claimed
        assert claimed["device"]["name"] == "iPhone 15"

        # Second claim attempt must fail
        second_claim = await claim_pairing_session(conn, code=code, device_name="Another Phone")
        assert second_claim is None


@pytest.mark.asyncio
async def test_expired_pairing_code(initialized_db):
    """Test that expired pairing codes cannot be claimed."""
    async with initialized_db.get_connection() as conn:
        host = await repository.register_device(
            conn, "Host PC", hash_token(generate_device_token())
        )

        past = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
        rec = await repository.create_pairing_code(
            conn, code="ARIA-EXPD", created_by_device_id=host["id"], expires_at=past
        )
        assert rec["code"] == "ARIA-EXPD"

        result = await claim_pairing_session(conn, code="ARIA-EXPD", device_name="Test Phone")
        assert result is None


@pytest.mark.asyncio
async def test_pairing_api_endpoints(async_client: AsyncClient):
    """Test HTTP API endpoints for pairing create, qr.svg, and claim."""
    client = async_client
    # Step 1: Initial host setup
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"password": "primary-password", "device_name": "Primary Desktop"},
    )
    assert login_resp.status_code == 200
    host_token = login_resp.json()["token"]

    # Step 2: Request pairing code with host auth
    create_resp = await client.post(
        "/api/v1/auth/pair/create",
        headers={"Authorization": f"Bearer {host_token}"},
        json={"ttl_seconds": 600},
    )
    assert create_resp.status_code == 200
    data = create_resp.json()
    code = data["code"]
    assert code.startswith("ARIA-")
    assert "qr_url" in data

    # Step 3: Fetch QR SVG
    qr_resp = await client.get(f"/api/v1/auth/pair/{code}/qr.svg")
    assert qr_resp.status_code == 200
    assert qr_resp.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in qr_resp.text

    # Step 4: Claim pairing code from secondary device
    claim_resp = await client.post(
        "/api/v1/auth/pair/claim",
        json={"code": code, "device_name": "Mobile Safari on iPhone"},
    )
    assert claim_resp.status_code == 200
    phone_auth = claim_resp.json()
    assert "token" in phone_auth
    assert phone_auth["device"]["name"] == "Mobile Safari on iPhone"
    phone_token = phone_auth["token"]

    # Verify phone token works for authenticated requests
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {phone_token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["name"] == "Mobile Safari on iPhone"

    # Verify claiming invalid/used code fails with 400
    fail_resp = await client.post(
        "/api/v1/auth/pair/claim",
        json={"code": code, "device_name": "Third Device"},
    )
    assert fail_resp.status_code == 400
