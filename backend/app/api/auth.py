"""Authentication routes for single-user password & device token management."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.sync_hub import sync_hub
from app.auth.pairing import (
    claim_pairing_session,
    create_pairing_session,
    generate_pairing_qr_svg,
)
from app.auth.security import (
    authenticate_or_init_master_password,
    generate_device_token,
    get_current_device,
    hash_token,
)
from app.db import repository
from app.db.connection import get_database

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, description="Master password")
    device_name: str | None = Field(default="Web Browser", description="Human-readable device name")


class LoginResponse(BaseModel):
    token: str
    device: dict[str, Any]
    first_time_setup: bool


class PairCreateRequest(BaseModel):
    ttl_seconds: int = Field(
        default=600, ge=60, le=3600, description="Validity duration in seconds"
    )


class PairCreateResponse(BaseModel):
    id: str
    code: str
    expires_at: str
    ttl_seconds: int
    qr_url: str


class PairClaimRequest(BaseModel):
    code: str = Field(..., min_length=4, description="Pairing code")
    device_name: str | None = Field(default="Mobile Client", description="Name for the new device")


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> LoginResponse:
    """
    Authenticate against master password, or set initial master password if fresh install.
    Returns a long random device token to be stored client-side.
    """
    db = get_database()
    async with db.get_connection() as conn:
        authenticated, first_time = await authenticate_or_init_master_password(conn, req.password)
        if not authenticated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect master password",
            )

        raw_token = generate_device_token()
        token_hash = hash_token(raw_token)
        device = await repository.register_device(
            conn,
            name=req.device_name or "Web Browser",
            token_hash=token_hash,
        )

        return LoginResponse(
            token=raw_token,
            device={
                "id": device["id"],
                "name": device["name"],
                "created_at": device["created_at"],
            },
            first_time_setup=first_time,
        )


@router.get("/me")
async def get_my_device(
    current_device: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Verify that the current device token is active and fetch device info."""
    return current_device


@router.get("/devices")
async def list_all_devices(
    _: dict[str, Any] = Depends(get_current_device),
) -> list[dict[str, Any]]:
    """List all paired devices."""
    db = get_database()
    async with db.get_connection() as conn:
        return await repository.list_devices(conn)


@router.post("/devices/{device_id}/revoke")
async def revoke_device(
    device_id: str,
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Revoke a device token by device ID and immediately terminate active connections."""
    db = get_database()
    async with db.get_connection() as conn:
        success = await repository.revoke_device(conn, device_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

        # Disconnect any live WebSockets associated with the revoked device
        await sync_hub.disconnect_device(device_id)
        return {"revoked": True, "device_id": device_id}


@router.post("/pair/create", response_model=PairCreateResponse)
async def create_pairing_code_endpoint(
    req: PairCreateRequest | None = None,
    current_device: dict[str, Any] = Depends(get_current_device),
) -> PairCreateResponse:
    """Generate a temporary pairing code & QR link for enrolling a secondary device."""
    ttl = req.ttl_seconds if req else 600
    db = get_database()
    async with db.get_connection() as conn:
        session_info = await create_pairing_session(
            conn,
            created_by_device_id=current_device["id"],
            ttl_seconds=ttl,
        )
        return PairCreateResponse(
            id=session_info["id"],
            code=session_info["code"],
            expires_at=session_info["expires_at"],
            ttl_seconds=session_info["ttl_seconds"],
            qr_url=f"/api/v1/auth/pair/{session_info['code']}/qr.svg",
        )


@router.get("/pair/{code}/qr.svg")
async def get_pairing_qr_svg_endpoint(code: str) -> Response:
    """Generate and return an SVG QR code for the given pairing code."""
    db = get_database()
    async with db.get_connection() as conn:
        record = await repository.get_pairing_code(conn, code.upper())
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Pairing code not found"
            )

    # Generate QR with URL path format `/?pair=<code>`
    qr_svg = generate_pairing_qr_svg(f"/?pair={code.upper()}")
    return Response(content=qr_svg, media_type="image/svg+xml")


@router.post("/pair/claim", response_model=LoginResponse)
async def claim_pairing_code_endpoint(req: PairClaimRequest) -> LoginResponse:
    """Claim a valid pairing code to register a new device without exposing master password."""
    db = get_database()
    async with db.get_connection() as conn:
        result = await claim_pairing_session(
            conn,
            code=req.code,
            device_name=req.device_name or "Mobile Client",
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired pairing code",
            )

        device = result["device"]
        return LoginResponse(
            token=result["token"],
            device={
                "id": device["id"],
                "name": device["name"],
                "created_at": device["created_at"],
            },
            first_time_setup=False,
        )
