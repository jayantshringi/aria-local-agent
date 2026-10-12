"""High-performance LRU and persistent embedding cache for nomic-embed-text."""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict

logger = logging.getLogger("aria.memory.cache")


class EmbeddingCache:
    """In-memory LRU cache for computed text embeddings to minimize Ollama inference overhead."""

    def __init__(self, capacity: int = 2048) -> None:
        self.capacity = max(1, capacity)
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _compute_key(text: str, model: str) -> str:
        """Create a deterministic cache key from normalized text and model name."""
        norm_text = text.strip()
        digest = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()
        return f"{model}:{digest}"

    def get(self, text: str, model: str) -> list[float] | None:
        """Retrieve cached embedding vector if present."""
        key = self._compute_key(text, model)
        if key in self._cache:
            self._hits += 1
            # Move to end to mark as recently used
            self._cache.move_to_end(key)
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, text: str, model: str, embedding: list[float]) -> None:
        """Store embedding vector into LRU cache."""
        if not embedding or not text.strip():
            return

        key = self._compute_key(text, model)
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.capacity:
                # Evict oldest item
                self._cache.popitem(last=False)
        self._cache[key] = embedding

    def clear(self) -> None:
        """Flush the cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict[str, int | float]:
        """Return cache hit/miss statistics and utilization."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total) if total > 0 else 0.0
        return {
            "size": len(self._cache),
            "capacity": self.capacity,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
        }


# Global singleton instance
_embedding_cache_instance: EmbeddingCache | None = None


def get_embedding_cache() -> EmbeddingCache:
    """Return the global EmbeddingCache singleton."""
    global _embedding_cache_instance
    if _embedding_cache_instance is None:
        from app.config import get_settings

        settings = get_settings()
        _embedding_cache_instance = EmbeddingCache(capacity=settings.embedding_cache_size)
    return _embedding_cache_instance
