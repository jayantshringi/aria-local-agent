"""Tests for Phase 2: Memory, sqlite-vec, hybrid search, profile facts, and summarization."""

import pytest
from httpx import AsyncClient

from app.db import repository
from app.db.connection import get_database
from app.memory.embeddings import EMBEDDING_DIM, EmbeddingClient
from app.memory.extractor import extract_heuristic_facts, process_and_store_candidate_facts
from app.memory.profile import (
    approve_fact,
    format_facts_for_prompt,
    get_approved_facts,
    reject_fact,
    remove_fact,
)
from app.memory.retrieval import format_memories_for_prompt, hybrid_search
from app.memory.summarizer import summarize_session


@pytest.mark.asyncio
async def test_embedding_client_fallback() -> None:
    """Embedding client generates valid 768-dim normalized vectors offline."""
    client = EmbeddingClient(base_url="http://127.0.0.1:99999")  # Unreachable port
    vec = await client.get_embedding("Hello local world")
    assert len(vec) == EMBEDDING_DIM
    assert isinstance(vec[0], float)

    # Empty text check
    empty_vec = await client.get_embedding("")
    assert len(empty_vec) == EMBEDDING_DIM
    assert all(x == 0.0 for x in empty_vec)


@pytest.mark.asyncio
async def test_sqlite_vec_chunk_insertion_and_search() -> None:
    """Verify sqlite-vec virtual table indexing and similarity search."""
    db = get_database()
    embed = EmbeddingClient()

    async with db.get_connection() as conn:
        text1 = "SQLite WAL mode with sqlite-vec provides ultra fast local vector search."
        text2 = "Baking chocolate chip cookies requires butter, brown sugar, and flour."

        vec1 = await embed.get_embedding(text1)
        vec2 = await embed.get_embedding(text2)

        c1 = await repository.create_memory_chunk(
            conn, source_type="note", source_id="note_1", text=text1, embedding=vec1
        )
        c2 = await repository.create_memory_chunk(
            conn, source_type="recipe", source_id="rec_1", text=text2, embedding=vec2
        )

        assert c1["id"] is not None
        assert c2["id"] is not None

        # Query vector search with text1
        results = await repository.search_memory_vectors(conn, query_embedding=vec1, limit=5)
        assert len(results) >= 1
        top_match = results[0]
        assert top_match["chunk_id"] == c1["id"]
        assert "sqlite-vec" in top_match["text"]


@pytest.mark.asyncio
async def test_hybrid_search() -> None:
    """Verify Reciprocal Rank Fusion over FTS5 keywords and vector similarity."""
    db = get_database()
    embed = EmbeddingClient()

    async with db.get_connection() as conn:
        # Create session and message for FTS5
        sess = await repository.create_session(conn, title="Architecture Discussion")
        msg = await repository.create_message(
            conn,
            session_id=sess["id"],
            role="user",
            content=(
                "We decided to use Piper for text-to-speech "
                "because it runs locally with zero telemetry."
            ),
        )

        # Index chunk in vector store
        vec = await embed.get_embedding(msg["content"])
        await repository.create_memory_chunk(
            conn,
            source_type="message",
            source_id=msg["id"],
            text=msg["content"],
            embedding=vec,
        )

        # Execute hybrid search
        results = await hybrid_search(conn, query="Piper text to speech", limit=5)
        assert len(results) > 0
        assert any("Piper" in r["text"] for r in results)

        # Format memories for prompt
        prompt_block = format_memories_for_prompt(results)
        assert "## Relevant Past Memories (Context)" in prompt_block
        assert "Piper" in prompt_block


@pytest.mark.asyncio
async def test_profile_facts_approval_gate() -> None:
    """Hard rule: Only approved facts enter prompt context."""
    db = get_database()

    async with db.get_connection() as conn:
        # 1. Propose candidate fact (pending)
        f_pending = await repository.create_profile_fact(
            conn, key="IDE", value="Google Antigravity", status="pending"
        )
        assert f_pending["status"] == "pending"

        # Check approved facts query
        approved_initial = await get_approved_facts(conn)
        assert not any(f["key"] == "IDE" for f in approved_initial)

        # Prompt formatting must NOT contain pending fact
        prompt_txt = format_facts_for_prompt(approved_initial)
        assert "Google Antigravity" not in prompt_txt

        # 2. Approve the fact
        updated = await approve_fact(conn, f_pending["id"])
        assert updated is not None
        assert updated["status"] == "approved"

        # Now it enters approved facts & prompt
        approved_after = await get_approved_facts(conn)
        assert any(f["key"] == "IDE" and f["value"] == "Google Antigravity" for f in approved_after)
        prompt_txt = format_facts_for_prompt(approved_after)
        assert "Google Antigravity" in prompt_txt

        # 3. Reject fact -> leaves prompt
        rejected = await reject_fact(conn, f_pending["id"])
        assert rejected is not None
        assert rejected["status"] == "rejected"
        approved_rejected = await get_approved_facts(conn)
        assert not any(f["key"] == "IDE" for f in approved_rejected)

        # 4. Remove fact
        deleted = await remove_fact(conn, f_pending["id"])
        assert deleted is True


@pytest.mark.asyncio
async def test_fact_extractor_and_heuristics() -> None:
    """Heuristic extraction finds user facts and marks them pending."""
    heuristics = extract_heuristic_facts("Hello, my name is Alex and I live in Munich.")
    assert len(heuristics) >= 2
    keys = {h["key"] for h in heuristics}
    assert "User Name" in keys
    assert "Location" in keys

    db = get_database()
    async with db.get_connection() as conn:
        stored = await process_and_store_candidate_facts(
            conn, "Hello! My name is Arthur Pendragon and I speak Welsh."
        )
        assert len(stored) >= 1
        for f in stored:
            assert f["status"] == "pending"


@pytest.mark.asyncio
async def test_session_summarizer() -> None:
    """Summarizer creates summary for multi-message session and indexes it."""
    db = get_database()

    async with db.get_connection() as conn:
        session = await repository.create_session(conn, title="Project Setup")
        await repository.create_message(
            conn, session_id=session["id"], role="user", content="How do we configure sqlite-vec?"
        )
        await repository.create_message(
            conn,
            session_id=session["id"],
            role="assistant",
            content="Load extension sqlite_vec.loadable_path() on connection startup.",
        )

        summary = await summarize_session(conn, session["id"])
        assert summary is not None
        assert len(summary) > 5

        # Check session updated
        refreshed = await repository.get_session(conn, session["id"])
        assert refreshed["summary"] == summary


@pytest.mark.asyncio
async def test_memory_api_endpoints(async_client: AsyncClient) -> None:
    """Verify REST endpoints for memory search and profile facts."""
    # Login to acquire device token
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"password": "TestPasswordMemory", "device_name": "Memory Test PC"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a fact via API
    create_res = await async_client.post(
        "/api/v1/memory/facts",
        headers=headers,
        json={"key": "Favorite OS", "value": "Linux", "status": "approved"},
    )
    assert create_res.status_code == 201
    fact_id = create_res.json()["id"]

    # 2. List facts
    list_res = await async_client.get("/api/v1/memory/facts", headers=headers)
    assert list_res.status_code == 200
    facts = list_res.json()
    assert any(f["id"] == fact_id for f in facts)

    # 3. Patch fact status to rejected
    patch_res = await async_client.patch(
        f"/api/v1/memory/facts/{fact_id}",
        headers=headers,
        json={"status": "rejected"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "rejected"

    # 4. Search memory endpoint
    search_res = await async_client.get(
        "/api/v1/memory/search",
        headers=headers,
        params={"q": "Favorite OS"},
    )
    assert search_res.status_code == 200
    assert isinstance(search_res.json(), list)

    # 5. Delete fact
    del_res = await async_client.delete(f"/api/v1/memory/facts/{fact_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json() == {"deleted": True}
