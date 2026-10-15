"""Unified Vector Memory engine with dense vector similarity and hybrid search."""

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from app.db import repository
from app.db.connection import get_database
from app.memory.embeddings import EmbeddingClient
from app.memory.profile import get_approved_facts
from app.memory.retrieval import hybrid_search

logger = logging.getLogger("aria.core.memory")


@dataclass
class VectorRecord:
    """An individual vector memory entry."""

    id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


class InMemoryVectorStore:
    """Chroma/FAISS compatible local in-memory cosine similarity vector index."""

    def __init__(self, dimension: int = 768) -> None:
        self.dimension = dimension
        self._records: dict[str, VectorRecord] = {}

    def add(
        self,
        record_id: str,
        text: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add or update an embedding record."""
        self._records[record_id] = VectorRecord(
            id=record_id,
            text=text,
            embedding=embedding,
            metadata=metadata or {},
        )

    def delete(self, record_id: str) -> bool:
        """Delete a record by id."""
        if record_id in self._records:
            del self._records[record_id]
            return True
        return False

    def count(self) -> int:
        """Return total count of indexed vectors."""
        return len(self._records)

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[tuple[VectorRecord, float]]:
        """Query top-k nearest records by cosine similarity."""
        if not self._records or not query_embedding:
            return []

        scored = []
        for rec in self._records.values():
            sim = self._cosine_similarity(query_embedding, rec.embedding)
            scored.append((rec, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)


class VectorMemory:
    """Unified Vector Memory supporting dense vector search (sqlite-vec), in-memory FAISS/Chroma store, and hybrid search."""

    def __init__(self) -> None:
        self.embed_client = EmbeddingClient()
        self.in_memory_index = InMemoryVectorStore(dimension=768)

    async def search(
        self,
        query: str,
        limit: int = 5,
        token_budget: int = 800,
    ) -> list[dict[str, Any]]:
        """Perform hybrid search over persistent sqlite-vec and FTS5 memory."""
        db = get_database()
        async with db.get_connection() as conn:
            return await hybrid_search(
                conn,
                query=query,
                limit=limit,
                token_budget=token_budget,
            )

    async def store(
        self,
        source_type: str,
        text: str,
        source_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Embed text and persist chunk into sqlite-vec and in-memory index."""
        embedding = await self.embed_client.get_embedding(text)
        db = get_database()
        async with db.get_connection() as conn:
            chunk = await repository.create_memory_chunk(
                conn,
                source_type=source_type,
                source_id=source_id,
                text=text,
                embedding=embedding,
            )
            chunk_id = chunk["id"]

        self.in_memory_index.add(
            record_id=chunk_id,
            text=text,
            embedding=embedding,
            metadata={"source_type": source_type, "source_id": source_id, **(metadata or {})},
        )
        return chunk_id

    async def get_facts(self) -> list[dict[str, Any]]:
        """Fetch all approved user profile facts."""
        db = get_database()
        async with db.get_connection() as conn:
            return await get_approved_facts(conn)


# Global VectorMemory singleton
vector_memory = VectorMemory()

__all__ = ["VectorMemory", "InMemoryVectorStore", "VectorRecord", "vector_memory"]
