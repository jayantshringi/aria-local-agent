"""Tests for Ollama client and persona loading."""

import json
from pathlib import Path

import httpx
import pytest

from app.llm.ollama_client import OllamaClient
from app.llm.persona import DEFAULT_PERSONA_CONTENT, load_persona, save_persona


def test_persona_creation_and_modification(tmp_path: Path):
    """Test persona prompt initialization and update."""
    persona_file = tmp_path / "persona.md"

    # Auto-initialize
    content = load_persona(persona_file)
    assert content == DEFAULT_PERSONA_CONTENT.strip()
    assert persona_file.exists()

    # Modify
    custom = "You are a custom AI butler."
    save_persona(custom, persona_file)
    assert load_persona(persona_file) == custom


@pytest.mark.asyncio
async def test_ollama_client_offline_diagnostics():
    """Verify OllamaClient diagnostics when server port is unreachable."""
    # Use non-existent port
    client = OllamaClient(base_url="http://127.0.0.1:59999", timeout=1.0)
    health = await client.check_health()
    assert health["available"] is False
    assert health["error"] is not None
    assert "Could not connect to Ollama" in health["error"]


@pytest.mark.asyncio
async def test_ollama_client_mock_streaming(monkeypatch):
    """Test streaming generator parsing chunks and completion metadata."""
    mock_lines = [
        json.dumps({"message": {"role": "assistant", "content": "Hello"}, "done": False}) + "\n",
        json.dumps({"message": {"role": "assistant", "content": " world!"}, "done": False}) + "\n",
        json.dumps({"done": True, "eval_count": 2, "model": "qwen2.5:7b-instruct"}) + "\n",
    ]

    async def mock_aiter_lines(*args, **kwargs):
        for line in mock_lines:
            yield line

    class MockStreamResponse:
        status_code = 200

        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def aiter_lines(self):
            return mock_aiter_lines()

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url, **kwargs):
            return MockStreamResponse()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    client = OllamaClient()
    deltas = []
    total_tokens = 0

    async for chunk in client.stream_chat([{"role": "user", "content": "Hi"}]):
        if chunk["type"] == "delta":
            deltas.append(chunk["content"])
        elif chunk["type"] == "done":
            total_tokens = chunk["tokens"]

    assert "".join(deltas) == "Hello world!"
    assert total_tokens == 2
