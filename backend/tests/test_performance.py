"""Tests for performance optimizations (embedding cache and context-window management)."""

from app.llm.context import ContextWindowManager, estimate_tokens
from app.memory.cache import EmbeddingCache


def test_embedding_cache_operations():
    """Verify LRU cache hits, misses, and capacity eviction."""
    cache = EmbeddingCache(capacity=3)
    assert cache.stats()["size"] == 0
    assert cache.stats()["hit_rate"] == 0.0

    # Miss on empty
    vec1 = [0.1] * 768
    assert cache.get("hello", "nomic-embed-text") is None
    assert cache.stats()["misses"] == 1

    # Put and hit
    cache.put("hello", "nomic-embed-text", vec1)
    retrieved = cache.get("hello", "nomic-embed-text")
    assert retrieved == vec1
    assert cache.stats()["hits"] == 1
    assert cache.stats()["hit_rate"] == 0.5  # 1 hit, 1 miss

    # Fill to capacity
    vec2 = [0.2] * 768
    vec3 = [0.3] * 768
    vec4 = [0.4] * 768
    cache.put("world", "nomic-embed-text", vec2)
    cache.put("apple", "nomic-embed-text", vec3)
    assert cache.stats()["size"] == 3

    # Add 4th item -> should evict least recently used ("hello" was used before world and apple)
    # Touch "hello" so "world" becomes oldest
    cache.get("hello", "nomic-embed-text")
    cache.put("banana", "nomic-embed-text", vec4)

    assert cache.get("world", "nomic-embed-text") is None  # evicted!
    assert cache.get("hello", "nomic-embed-text") == vec1
    assert cache.get("banana", "nomic-embed-text") == vec4

    cache.clear()
    assert cache.stats()["size"] == 0


def test_context_window_estimation():
    """Verify subword token estimation behaves predictably."""
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello") >= 1
    short_text = "The quick brown fox jumps over the lazy dog."
    est = estimate_tokens(short_text)
    assert 5 <= est <= 15


def test_context_window_pruning():
    """Verify ContextWindowManager prunes older messages to protect token budget."""
    mgr = ContextWindowManager(max_context_tokens=1500, completion_reserve=500)
    # Available budget: 1000 tokens

    messages = [
        {"role": "user", "content": "Question 1 " * 50},  # ~150 tokens
        {"role": "assistant", "content": "Answer 1 " * 100},  # ~300 tokens
        {"role": "user", "content": "Question 2 " * 50},  # ~150 tokens
        {"role": "assistant", "content": "Answer 2 " * 100},  # ~300 tokens
        {"role": "user", "content": "Latest query"},  # ~3 tokens
    ]

    # Without high system overhead, all fit
    pruned_all = mgr.prune_messages(messages, system_overhead=50)
    assert len(pruned_all) == 5

    # With high system overhead (700 tokens), older messages must be pruned
    pruned_tight = mgr.prune_messages(messages, system_overhead=700)
    assert len(pruned_tight) < len(messages)
    # Most recent message must always be preserved
    assert pruned_tight[-1]["content"] == "Latest query"


def test_context_budget_breakdown():
    """Verify token budget breakdown calculations."""
    mgr = ContextWindowManager(max_context_tokens=4096, completion_reserve=1024)
    budget = mgr.calculate_budget(
        system_text="System instructions " * 20,
        facts_text="Fact: Owner likes Python.",
        memories_text="Memory snippet 1.",
    )
    assert budget["max_context"] == 4096
    assert budget["completion_reserve"] == 1024
    assert budget["prompt_budget"] == 3072
    assert budget["system_overhead"] > 0
    assert budget["history_allowance"] > 0
