"""Memory retrieval, embeddings, profile facts, and session summarization."""

from app.memory.embeddings import EmbeddingClient
from app.memory.extractor import process_and_store_candidate_facts
from app.memory.profile import (
    approve_fact,
    format_facts_for_prompt,
    get_all_facts,
    get_approved_facts,
    reject_fact,
    remove_fact,
    set_fact,
)
from app.memory.retrieval import format_memories_for_prompt, hybrid_search
from app.memory.summarizer import summarize_session

__all__ = [
    "EmbeddingClient",
    "hybrid_search",
    "format_memories_for_prompt",
    "get_approved_facts",
    "get_all_facts",
    "approve_fact",
    "reject_fact",
    "set_fact",
    "remove_fact",
    "format_facts_for_prompt",
    "process_and_store_candidate_facts",
    "summarize_session",
]
