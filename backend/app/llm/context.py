"""Context window management and token budget optimization for local LLMs."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("aria.llm.context")


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a text string using standard subword heuristic.
    Averages ~4 characters per token for English text and code, with a minimum of 1.
    """
    if not text:
        return 0
    # Words + punctuation heuristic
    char_len = len(text)
    words = len(text.split())
    # Blend word count (1.3 tokens/word) and char count (4 chars/token)
    token_est = int((words * 1.3 + char_len / 4.0) / 2.0)
    return max(1, token_est)


class ContextWindowManager:
    """Manages token allocation and sliding-window pruning for conversation context."""

    def __init__(self, max_context_tokens: int = 4096, completion_reserve: int = 1024) -> None:
        self.max_context_tokens = max(1024, max_context_tokens)
        self.completion_reserve = completion_reserve
        # Available tokens for input prompt
        self.prompt_budget = max(512, self.max_context_tokens - self.completion_reserve)

    def prune_messages(
        self,
        messages: list[dict[str, Any]],
        system_overhead: int = 0,
        memory_overhead: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Prune message history so that system + memories + messages fits within prompt budget.
        Always preserves the most recent message(s). Removes oldest messages first.
        """
        if not messages:
            return []

        available_for_history = self.prompt_budget - system_overhead - memory_overhead
        if available_for_history < 200:
            # Fallback minimum window: at least the very last message
            available_for_history = 200

        # Start from newest and accumulate backwards
        selected: list[dict[str, Any]] = []
        accumulated_tokens = 0

        for msg in reversed(messages):
            content = msg.get("content", "")
            cost = estimate_tokens(content) + 4  # +4 for role framing tokens

            if selected and (accumulated_tokens + cost > available_for_history):
                # Cannot fit this older message without exceeding budget
                logger.debug(
                    f"Context pruning: Dropped older message (role={msg.get('role')}, tokens={cost})"
                )
                continue

            selected.append(msg)
            accumulated_tokens += cost

        # Restore chronological order
        selected.reverse()
        return selected

    def calculate_budget(
        self,
        system_text: str,
        facts_text: str,
        memories_text: str,
    ) -> dict[str, int]:
        """Calculate breakdown of token consumption across prompt components."""
        sys_tokens = estimate_tokens(system_text)
        facts_tokens = estimate_tokens(facts_text)
        mem_tokens = estimate_tokens(memories_text)
        fixed_overhead = sys_tokens + facts_tokens + mem_tokens

        history_allowance = max(0, self.prompt_budget - fixed_overhead)
        return {
            "max_context": self.max_context_tokens,
            "completion_reserve": self.completion_reserve,
            "prompt_budget": self.prompt_budget,
            "system_overhead": sys_tokens,
            "profile_facts_tokens": facts_tokens,
            "retrieved_memories_tokens": mem_tokens,
            "history_allowance": history_allowance,
        }
