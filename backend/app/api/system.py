"""System administration, hardware telemetry, model switching, and data maintenance API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.agent.plugins import load_plugins_from_directory
from app.agent.registry import tool_registry
from app.auth.security import get_current_device
from app.config import get_settings
from app.db.connection import get_database
from app.system.export import export_full_data_json, generate_export_zip
from app.system.models import (
    get_active_chat_model,
    list_installed_ollama_models,
    set_active_chat_model,
)
from app.system.resources import get_system_telemetry
from app.system.wipe import CONFIRMATION_REQUIRED_STRING, wipe_all_user_data

logger = logging.getLogger("aria.api.system")
router = APIRouter(prefix="/api/v1/system", tags=["system"])


class SelectModelRequest(BaseModel):
    model: str = Field(..., min_length=1, description="Ollama model identifier")


class WipeDataRequest(BaseModel):
    confirmation: str = Field(..., description="Confirmation phrase to execute wipe")


@router.get("/resources")
async def read_system_resources(
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Retrieve host telemetry (CPU, RAM, storage, uptime, and embedding cache stats)."""
    return get_system_telemetry()


@router.get("/models")
async def read_models(
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """List available local Ollama models and current active model."""
    db = get_database()
    async with db.get_connection() as conn:
        active_chat = await get_active_chat_model(conn)

    ollama_info = await list_installed_ollama_models()
    settings = get_settings()

    return {
        "active_chat_model": active_chat,
        "configured_embed_model": settings.ollama_embed_model,
        "ollama_online": ollama_info.get("ollama_online", False),
        "models": ollama_info.get("models", []),
    }


@router.post("/models/select")
async def select_model(
    req: SelectModelRequest,
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Switch the default chat model for future interactions and persist to SQLite settings."""
    db = get_database()
    async with db.get_connection() as conn:
        saved_name = await set_active_chat_model(conn, req.model)

    return {
        "success": True,
        "active_chat_model": saved_name,
    }


@router.get("/export")
async def export_data(
    format: str = Query(default="json", pattern="^(json|zip)$"),
    _: dict[str, Any] = Depends(get_current_device),
) -> Response:
    """Export complete user data (sessions, messages, profile facts, reminders, audit log)."""
    db = get_database()
    async with db.get_connection() as conn:
        data = await export_full_data_json(conn)

    if format == "zip":
        zip_bytes = generate_export_zip(data)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=aria-export.zip"},
        )

    # Default to json
    return JSONResponse(content=data)


@router.get("/export/json")
async def export_data_json(
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Export complete user data as JSON."""
    db = get_database()
    async with db.get_connection() as conn:
        return await export_full_data_json(conn)


@router.post("/wipe")
async def wipe_data(
    req: WipeDataRequest,
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Permanently delete all user sessions, memories, profile facts, and audit records."""
    if req.confirmation.strip() != CONFIRMATION_REQUIRED_STRING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid confirmation phrase. Must be '{CONFIRMATION_REQUIRED_STRING}'",
        )

    db = get_database()
    async with db.get_connection() as conn:
        res = await wipe_all_user_data(conn, req.confirmation)

    return res


@router.get("/plugins")
async def list_plugins(
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """List loaded dynamic tool plugins and current plugin directory path."""
    settings = get_settings()
    plugins_dir = settings.plugins_dir_path

    # All tools in registry
    all_tools = tool_registry.get_catalog_summary()
    return {
        "plugins_dir": str(plugins_dir),
        "registered_tools_count": len(all_tools),
        "tools": all_tools,
    }


@router.post("/plugins/rescan")
async def rescan_plugins(
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Scan ~/.aria/plugins/ and load newly added tool plugins without restarting."""
    loaded = load_plugins_from_directory()
    return {
        "success": True,
        "newly_loaded_plugins": loaded,
    }
