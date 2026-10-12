"""Integration tests for System API endpoints (resources, models, export, wipe, plugins)."""

import io
import zipfile

import pytest
from httpx import AsyncClient


async def _get_authenticated_headers(client: AsyncClient) -> dict[str, str]:
    """Helper to authenticate a device and return Bearer headers."""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"password": "MyMasterPassword", "device_name": "Test Device"},
    )
    token = login_resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_system_resources_endpoint(async_client: AsyncClient):
    """Verify /api/v1/system/resources returns telemetry without network access."""
    headers = await _get_authenticated_headers(async_client)
    res = await async_client.get("/api/v1/system/resources", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "cpu" in data
    assert "memory" in data
    assert "disk" in data
    assert "platform" in data
    assert "uptime_seconds" in data
    assert "embedding_cache" in data
    assert data["cpu"]["cores"] >= 1


@pytest.mark.asyncio
async def test_system_models_management(async_client: AsyncClient):
    """Verify /api/v1/system/models querying and dynamic switching."""
    headers = await _get_authenticated_headers(async_client)

    # 1. Read models
    res = await async_client.get("/api/v1/system/models", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "active_chat_model" in data
    assert "models" in data

    # 2. Switch model
    sel_res = await async_client.post(
        "/api/v1/system/models/select",
        headers=headers,
        json={"model": "llama3.1:8b-instruct-q4"},
    )
    assert sel_res.status_code == 200
    assert sel_res.json()["active_chat_model"] == "llama3.1:8b-instruct-q4"

    # 3. Verify switched model persists
    check_res = await async_client.get("/api/v1/system/models", headers=headers)
    assert check_res.json()["active_chat_model"] == "llama3.1:8b-instruct-q4"


@pytest.mark.asyncio
async def test_system_export_json_and_zip(async_client: AsyncClient):
    """Verify full data export in both JSON and ZIP archives."""
    headers = await _get_authenticated_headers(async_client)

    # Create a test session first
    await async_client.post(
        "/sessions",
        headers=headers,
        json={"title": "Session to Export"},
    )

    # 1. Test JSON export
    json_res = await async_client.get("/api/v1/system/export/json", headers=headers)
    assert json_res.status_code == 200
    exp_json = json_res.json()
    assert "sessions" in exp_json
    assert len(exp_json["sessions"]) >= 1
    assert "profile_facts" in exp_json

    # 2. Test ZIP export
    zip_res = await async_client.get("/api/v1/system/export?format=zip", headers=headers)
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"

    # Verify zip content
    with zipfile.ZipFile(io.BytesIO(zip_res.content), "r") as zf:
        namelist = zf.namelist()
        assert "aria_export.json" in namelist
        assert "profile_facts.md" in namelist
        # Session markdown should exist
        session_files = [n for n in namelist if n.startswith("sessions/")]
        assert len(session_files) >= 1


@pytest.mark.asyncio
async def test_system_wipe_flow(async_client: AsyncClient):
    """Verify data wipe requires correct confirmation phrase and deletes all records."""
    headers = await _get_authenticated_headers(async_client)

    # Create sample session
    await async_client.post("/sessions", headers=headers, json={"title": "Will Be Wiped"})

    # 1. Attempt wipe with invalid confirmation
    fail_res = await async_client.post(
        "/api/v1/system/wipe",
        headers=headers,
        json={"confirmation": "wrong_phrase"},
    )
    assert fail_res.status_code == 400

    # 2. Attempt wipe with correct confirmation
    wipe_res = await async_client.post(
        "/api/v1/system/wipe",
        headers=headers,
        json={"confirmation": "PERMANENTLY_DELETE_ALL_DATA"},
    )
    assert wipe_res.status_code == 200
    wipe_data = wipe_res.json()
    assert wipe_data["success"] is True

    # 3. Verify sessions table is now completely empty
    list_res = await async_client.get("/sessions", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 0


@pytest.mark.asyncio
async def test_system_plugins_endpoint(async_client: AsyncClient):
    """Verify listing and rescanning plugins."""
    headers = await _get_authenticated_headers(async_client)

    res = await async_client.get("/api/v1/system/plugins", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "plugins_dir" in data
    assert "tools" in data

    rescan = await async_client.post("/api/v1/system/plugins/rescan", headers=headers)
    assert rescan.status_code == 200
    assert rescan.json()["success"] is True
