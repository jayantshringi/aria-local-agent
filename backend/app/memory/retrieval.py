"""Hybrid memory retrieval combining FTS5 keyword matching and sqlite-vec similarity."""

import re
from typing import Any

import aiosqlite

from app.db import repository
from app.memory.embeddings import EmbeddingClient


def sanitize_fts5_query(query: str) -> str:
    """Sanitize query string to avoid FTS5 syntax errors."""
    clean = re.sub(r"[^\w\s]", " ", query)
    tokens = clean.strip().split()
    if not tokens:
        return ""
    # Use OR or simple token prefix
    return " OR ".join(tokens)


async def hybrid_search(
    conn: aiosqlite.Connection,
    query: str,
    limit: int = 5,
    token_budget: int = 1000,
) -> list[dict[str, Any]]:
    """
    Execute hybrid search using Reciprocal Rank Fusion (RRF) over FTS5 and sqlite-vec.
    Returns ranked memory items within the requested token budget.
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    # Map from normalized content -> merged item dict
    candidates: dict[str, dict[str, Any]] = {}
    RRF_K = 60

    # 1. Full-text search (FTS5)
    fts_search_term = sanitize_fts5_query(clean_query)
    if fts_search_term:
        try:
            fts_rows = await repository.search_messages_fts(conn, fts_search_term, limit=limit * 2)
            for idx, row in enumerate(fts_rows):
                text = row["content"].strip()
                if not text:
                    continue
                score = 1.0 / (RRF_K + idx + 1)
                if text not in candidates:
                    candidates[text] = {
                        "text": text,
                        "source_type": "message",
                        "source_id": row["id"],
                        "score": score,
                        "created_at": row.get("created_at", ""),
                    }
                else:
                    candidates[text]["score"] += score
        except Exception:
            pass

    # 2. Vector search (sqlite-vec)
    embed_client = EmbeddingClient()
    query_vec = await embed_client.get_embedding(clean_query)
    vec_rows = await repository.search_memory_vectors(conn, query_vec, limit=limit * 2)

    for idx, row in enumerate(vec_rows):
        text = row["text"].strip()
        if not text:
            continue
        score = 1.0 / (RRF_K + idx + 1)
        if text not in candidates:
            candidates[text] = {
                "text": text,
                "source_type": row.get("source_type", "memory_chunk"),
                "source_id": row.get("source_id", ""),
                "score": score,
                "created_at": row.get("created_at", ""),
            }
        else:
            candidates[text]["score"] += score

    # 3. Sort by fused score descending
    sorted_items = sorted(candidates.values(), key=lambda x: x["score"], reverse=True)

    # 4. Limit by count and token budget (approx 4 chars per token)
    results = []
    char_budget = token_budget * 4
    current_chars = 0

    for item in sorted_items:
        item_len = len(item["text"])
        if current_chars + item_len > char_budget and len(results) > 0:
            break
        results.append(item)
        current_chars += item_len
        if len(results) >= limit:
            break

    return results


def format_memories_for_prompt(memories: list[dict[str, Any]]) -> str:
    """Format retrieved memories into a markdown block for prompt context injection."""
    if not memories:
        return ""

    lines = ["## Relevant Past Memories (Context)"]
    for mem in memories:
        text = mem["text"].replace("\n", " ").strip()
        if len(text) > 200:
            text = text[:197] + "..."
        lines.append(f"- {text}")

    return "\n".join(lines)
