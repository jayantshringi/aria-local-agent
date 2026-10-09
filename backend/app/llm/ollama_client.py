"""Asynchronous Ollama client supporting streaming chat completions and diagnostics."""

import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.config import get_settings


class OllamaError(Exception):
    """Base exception for Ollama interactions."""

    pass


class OllamaConnectionError(OllamaError):
    """Raised when Ollama is not running or unreachable."""

    pass


class OllamaClient:
    """Client for local Ollama HTTP API."""

    def __init__(
        self,
        base_url: str | None = None,
        chat_model: str | None = None,
        embed_model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.chat_model = chat_model or settings.ollama_chat_model
        self.embed_model = embed_model or settings.ollama_embed_model
        self.timeout = timeout

    async def get_tags(self) -> list[dict[str, Any]]:
        """Fetch list of local models available in Ollama."""
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("models", [])
                return []
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as exc:
            msg = f"Could not connect to Ollama at {self.base_url}. Ensure Ollama is running."
            raise OllamaConnectionError(msg) from exc

    async def check_health(self) -> dict[str, Any]:
        """Check if Ollama is reachable and whether configured models are downloaded."""
        try:
            models = await self.get_tags()
            model_names = [m.get("name", "") for m in models]
            chat_available = any(
                self.chat_model in name or name.startswith(self.chat_model.split(":")[0])
                for name in model_names
            )
            embed_available = any(
                self.embed_model in name or name.startswith(self.embed_model.split(":")[0])
                for name in model_names
            )

            return {
                "available": True,
                "base_url": self.base_url,
                "configured_chat_model": self.chat_model,
                "configured_embed_model": self.embed_model,
                "chat_model_available": chat_available,
                "embed_model_available": embed_available,
                "installed_models": model_names,
                "error": None,
            }
        except OllamaConnectionError as e:
            return {
                "available": False,
                "base_url": self.base_url,
                "configured_chat_model": self.chat_model,
                "configured_embed_model": self.embed_model,
                "chat_model_available": False,
                "embed_model_available": False,
                "installed_models": [],
                "error": str(e),
            }

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Stream chat completion tokens from Ollama.
        Yields dictionaries with format:
          {"type": "delta", "content": "..."}
          or
          {"type": "done", "tokens": int, "model": str}
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model or self.chat_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        raw_err = await response.aread()
                        err_str = raw_err.decode("utf-8", errors="replace")
                        raise OllamaError(f"Ollama returned HTTP {response.status_code}: {err_str}")

                    async for line in response.aiter_lines():
                        if not line or not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Check token delta
                        msg = chunk.get("message", {})
                        content = msg.get("content", "")
                        if content:
                            yield {"type": "delta", "content": content}

                        # Check completion
                        if chunk.get("done", False):
                            eval_count = chunk.get("eval_count", 0)
                            yield {
                                "type": "done",
                                "tokens": eval_count,
                                "model": chunk.get("model", self.chat_model),
                            }
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            msg = f"Connection to Ollama at {self.base_url} failed during generation."
            raise OllamaConnectionError(msg) from exc
