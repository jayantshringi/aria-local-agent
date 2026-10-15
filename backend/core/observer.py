"""OPEC Agent Loop: Observer Component for ambient context, intent and multi-modal observation."""

import logging
import platform
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psutil

from app.config import get_settings

logger = logging.getLogger("aria.core.observer")


@dataclass
class Observation:
    """Structured observation produced by the Observer component."""

    user_input: str
    modalities: list[str] = field(default_factory=lambda: ["text"])
    intent: str = "general"
    extracted_entities: dict[str, Any] = field(default_factory=dict)
    ambient_state: dict[str, Any] = field(default_factory=dict)
    dialogue_context: list[dict[str, str]] = field(default_factory=list)
    relevant_memories: list[dict[str, Any]] = field(default_factory=list)
    approved_profile_facts: list[dict[str, Any]] = field(default_factory=list)


class Observer:
    """Gathers user query, ambient system context, semantic memories, and intent analysis."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def observe(
        self,
        user_input: str,
        session_id: str | None = None,
        history: list[dict[str, Any]] | None = None,
        modalities: list[str] | None = None,
    ) -> Observation:
        """Analyze user input and gather all relevant environment, memory, and dialogue context."""
        cleaned_input = (user_input or "").strip()
        mods = modalities or ["text"]

        # 1. Gather ambient host environment
        ambient = self._gather_ambient_state()

        # 2. Extract entities and identify intent
        entities = self._extract_entities(cleaned_input)
        intent = self._classify_intent(cleaned_input, entities)

        # 3. Retrieve relevant memories & approved facts from database
        memories: list[dict[str, Any]] = []
        facts: list[dict[str, Any]] = []

        try:
            from app.db.connection import get_database
            from app.memory.profile import get_approved_facts
            from app.memory.retrieval import hybrid_search

            db = get_database()
            async with db.get_connection() as conn:
                facts = await get_approved_facts(conn)
                if cleaned_input:
                    memories = await hybrid_search(
                        conn, query=cleaned_input, limit=5, token_budget=600
                    )
        except Exception as exc:
            logger.debug(f"Memory retrieval in Observer non-fatal notice: {exc}")

        # 4. Standardize dialogue context
        dialogue: list[dict[str, str]] = []
        if history:
            for item in history[-10:]:
                role = item.get("role", "user")
                content = item.get("content", "")
                if content:
                    dialogue.append({"role": role, "content": content})

        return Observation(
            user_input=cleaned_input,
            modalities=mods,
            intent=intent,
            extracted_entities=entities,
            ambient_state=ambient,
            dialogue_context=dialogue,
            relevant_memories=memories,
            approved_profile_facts=facts,
        )

    def _gather_ambient_state(self) -> dict[str, Any]:
        """Inspect host resources and whitelisted directories."""
        vm = psutil.virtual_memory()
        return {
            "os": platform.system(),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_percent": vm.percent,
            "whitelisted_roots": [str(d) for d in self.settings.whitelisted_directories],
            "active_language": self.settings.aria_language,
            "cwd": str(Path.cwd()),
        }

    def _extract_entities(self, text: str) -> dict[str, Any]:
        """Extract file paths, URLs, commands, and app mentions using deterministic patterns."""
        entities: dict[str, Any] = {
            "paths": [],
            "urls": [],
            "tools_mentioned": [],
        }

        # URL extraction
        url_pattern = r"https?://[^\s<>\"']+"
        entities["urls"] = re.findall(url_pattern, text)

        # Path/file extraction (extensions like .txt, .py, .md, .json, etc.)
        file_pattern = r"[\w\-\./\\]+\.(?:py|md|txt|json|html|css|js|ts|tsx|csv|log|bat|sh)\b"
        entities["paths"] = re.findall(file_pattern, text, re.IGNORECASE)

        # Tool hints
        lower = text.lower()
        if any(w in lower for w in ["search for", "find file", "look for", "list file"]):
            entities["tools_mentioned"].append("filesystem.search")
        if any(w in lower for w in ["read file", "open file", "cat ", "show me the file"]):
            entities["tools_mentioned"].append("filesystem.read")
        if any(w in lower for w in ["create file", "write to", "save to"]):
            entities["tools_mentioned"].append("filesystem.write")
        if any(w in lower for w in ["git status", "git diff", "git log", "git commit"]):
            entities["tools_mentioned"].append("git.action")
        if any(w in lower for w in ["browse", "open url", "visit ", "fetch webpage"]):
            entities["tools_mentioned"].append("browser.navigate")
        if any(w in lower for w in ["run command", "terminal", "execute "]):
            entities["tools_mentioned"].append("terminal.exec")
        if any(w in lower for w in ["remind me", "set reminder"]):
            entities["tools_mentioned"].append("reminders.create")
        if any(w in lower for w in ["take a note", "save note", "new note"]):
            entities["tools_mentioned"].append("notes.create")

        return entities

    def _classify_intent(self, text: str, entities: dict[str, Any]) -> str:
        """Classify high-level user intent."""
        lower = text.lower()
        if not text:
            return "empty"
        if any(p in lower for p in ["hello", "hi aria", "good morning", "hey", "who are you"]):
            return "chit_chat"
        if entities["tools_mentioned"]:
            return "task_execution"
        if "?" in text or any(
            lower.startswith(w) for w in ["what", "how", "why", "where", "can you"]
        ):
            return "information_query"
        return "general_instruction"


__all__ = ["Observer", "Observation"]
