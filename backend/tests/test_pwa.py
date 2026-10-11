"""Tests for Phase 3 PWA static delivery, web app manifest, and service worker."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_pwa_manifest_delivery(async_client: AsyncClient):
    """Verify that /manifest.json is served with proper metadata."""
    resp = await async_client.get("/manifest.json")
    assert resp.status_code == 200
    manifest = resp.json()
    assert manifest["name"] == "Aria Local Agent"
    assert manifest["short_name"] == "Aria"
    assert manifest["display"] == "standalone"
    assert len(manifest["icons"]) >= 2


@pytest.mark.asyncio
async def test_pwa_service_worker_delivery(async_client: AsyncClient):
    """Verify that /sw.js is served with offline shell and notification logic."""
    resp = await async_client.get("/sw.js")
    assert resp.status_code == 200
    text = resp.text
    assert "aria-shell-v1" in text
    assert "self.addEventListener('fetch'" in text
    assert "self.addEventListener('push'" in text
    assert "self.addEventListener('notificationclick'" in text


@pytest.mark.asyncio
async def test_pwa_icons_delivery(async_client: AsyncClient):
    """Verify that PWA SVG icons are delivered correctly."""
    resp = await async_client.get("/icons/icon-192.svg")
    assert resp.status_code == 200
    assert "<svg" in resp.text

    resp512 = await async_client.get("/icons/icon-512.svg")
    assert resp512.status_code == 200
    assert "<svg" in resp512.text


@pytest.mark.asyncio
async def test_pwa_html_shell_meta_tags(async_client: AsyncClient):
    """Verify that root HTML contains PWA manifest link and mobile status bar tags."""
    resp = await async_client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert 'rel="manifest"' in html
    assert "apple-mobile-web-app-capable" in html
    assert "theme-color" in html
