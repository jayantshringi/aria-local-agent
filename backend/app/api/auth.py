"""Authentication routes for single-user password & device token management."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

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
    """Revoke a device token by device ID."""
    db = get_database()
    async with db.get_connection() as conn:
        success = await repository.revoke_device(conn, device_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
        return {"revoked": True, "device_id": device_id}
