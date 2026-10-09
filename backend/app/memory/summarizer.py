"""Session summarizer for idle or completed chat sessions."""

import logging

import aiosqlite
import httpx

from app.config import get_settings
from app.db import repository
from app.memory.embeddings import EmbeddingClient

logger = logging.getLogger("aria.summarizer")


async def summarize_session(conn: aiosqlite.Connection, session_id: str) -> str | None:
    """
    Generate and store a concise summary of a chat session.
    Saves summary to sessions table and indexes it in memory_chunks + memory_vectors.
    """
    session = await repository.get_session(conn, session_id)
    if not session:
        return None

    messages = await repository.list_messages(conn, session_id, limit=100)
    if len(messages) < 2:
        return None

    # Format transcript
    lines = []
    for msg in messages:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    transcript = "\n".join(lines)

    # Attempt LLM summarization
    summary: str | None = None
    settings = get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"

    prompt = (
        "You are an AI assistant. Provide a concise 1-3 sentence summary of this conversation, "
        "highlighting the core topics, questions answered, and any decisions reached. "
        "Do NOT include meta commentary. Be direct.\n\n"
        f"Conversation:\n{transcript}\n\n"
        "Summary:"
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                url,
                json={
                    "model": settings.ollama_chat_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            if res.status_code == 200:
                data = res.json()
                text = data.get("response", "").strip()
                if text:
                    summary = text
    except Exception as e:
        logger.debug(f"LLM session summarization offline/failed: {e}")

    # Fallback heuristic summary if LLM failed
    if not summary:
        first_user = next((m["content"] for m in messages if m["role"] == "user"), "")
        summary = f"Conversation discussing: {first_user[:100]}..."

    # Update session summary in DB
    await repository.update_session(conn, session_id=session_id, summary=summary)

    # Index summary chunk in memory_chunks and sqlite-vec
    try:
        embed_client = EmbeddingClient()
        chunk_text = f"Session summary ({session.get('title', 'Chat')}): {summary}"
        vec = await embed_client.get_embedding(chunk_text)
        await repository.create_memory_chunk(
            conn,
            source_type="session_summary",
            source_id=session_id,
            text=chunk_text,
            embedding=vec,
        )
    except Exception as e:
        logger.warning(f"Failed to index session summary embedding: {e}")

    return summary
