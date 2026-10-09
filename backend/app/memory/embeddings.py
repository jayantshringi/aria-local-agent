"""Embedding generator using Ollama nomic-embed-text with deterministic offline fallback."""

import hashlib
import logging
import math

import httpx

from app.config import get_settings

logger = logging.getLogger("aria.embeddings")
EMBEDDING_DIM = 768


def _deterministic_offline_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """
    Generate a normalized deterministic pseudo-embedding from text hash.
    Used when Ollama is offline so tests, indexing, and vector queries never fail.
    """
    vec = []
    # Seed hashing across dimensions
    base_bytes = text.strip().encode("utf-8")
    for i in range(dim):
        h = hashlib.sha256(base_bytes + i.to_bytes(2, "little")).digest()
        # Convert first 4 bytes to float between -1.0 and 1.0
        val = int.from_bytes(h[:4], "little", signed=True) / (2**31)
        vec.append(val)

    # Normalize L2 norm
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


class EmbeddingClient:
    """Client for generating dense vector embeddings via local Ollama."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_embed_model
        self.timeout = timeout

    async def get_embedding(self, text: str) -> list[float]:
        """
        Embed a text string using nomic-embed-text.
        Falls back gracefully to deterministic vector if Ollama is unreachable.
        """
        clean_text = text.strip()
        if not clean_text:
            return [0.0] * EMBEDDING_DIM

        # Try Ollama /api/embeddings or /api/embed
        url = f"{self.base_url}/api/embeddings"
        payload = {"model": self.model, "prompt": clean_text}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    vec = data.get("embedding", [])
                    if len(vec) == EMBEDDING_DIM:
                        return vec
                    elif len(vec) > 0:
                        # Pad or trim if model dimension differs
                        if len(vec) < EMBEDDING_DIM:
                            return vec + [0.0] * (EMBEDDING_DIM - len(vec))
                        return vec[:EMBEDDING_DIM]
        except Exception as e:
            logger.debug(f"Ollama embed call failed, using deterministic fallback: {e}")

        return _deterministic_offline_embedding(clean_text, EMBEDDING_DIM)
