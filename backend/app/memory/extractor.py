"""Extract candidate user profile facts from conversation text into pending facts."""

import json
import logging
import re
from typing import Any

import aiosqlite
import httpx

from app.config import get_settings
from app.db import repository

logger = logging.getLogger("aria.extractor")

# Basic heuristics for offline / fast extraction
HEURISTIC_PATTERNS: list[tuple[str, str]] = [
    (r"\bmy name is ([A-Z][a-zA-Z\s]+)", "User Name"),
    (r"\bi am a ([a-zA-Z\s]+developer|engineer|designer|manager|student)", "Role"),
    (r"\bi prefer ([a-zA-Z0-9\s,\-\+]+) over ", "Preference"),
    (r"\bi speak ([A-Z][a-z]+)", "Language"),
    (r"\bi live in ([A-Z][a-zA-Z\s,]+)", "Location"),
    (r"\bmy favorite (language|framework|tool) is ([a-zA-Z0-9\+\#\.]+)", "Favorite {0}"),
]


def extract_heuristic_facts(text: str) -> list[dict[str, Any]]:
    """Heuristic regex extraction for immediate/offline facts."""
    facts = []
    for pattern, key_template in HEURISTIC_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 1:
                val = groups[0].strip().rstrip(".")
                facts.append({"key": key_template, "value": val, "confidence": 0.8})
            elif len(groups) == 2:
                key = key_template.format(groups[0].capitalize())
                val = groups[1].strip().rstrip(".")
                facts.append({"key": key, "value": val, "confidence": 0.8})
    return facts


async def extract_facts_with_llm(text: str) -> list[dict[str, Any]]:
    """Extract candidate facts using local Ollama model if available."""
    settings = get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"

    prompt = (
        "You are an AI fact extraction system. Extract any persistent facts about the user "
        "from the following user text. Facts should be personal identity, preferred languages, "
        "tools, timezone, location, hardware, or explicit preferences.\n"
        "Do NOT extract temporary commands or questions.\n"
        "Return ONLY a valid JSON array of objects with keys 'key' and 'value'. "
        "If there are no facts, return [].\n\n"
        f'User text:\n"""{text}"""\n\n'
        "JSON output:"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(
                url,
                json={
                    "model": settings.ollama_chat_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            if res.status_code == 200:
                data = res.json()
                raw_response = data.get("response", "").strip()
                # Parse JSON
                parsed = json.loads(raw_response)
                if isinstance(parsed, list):
                    results = []
                    for item in parsed:
                        if isinstance(item, dict) and "key" in item and "value" in item:
                            results.append(
                                {
                                    "key": str(item["key"]).strip(),
                                    "value": str(item["value"]).strip(),
                                    "confidence": 0.85,
                                }
                            )
                    return results
                elif isinstance(parsed, dict) and "facts" in parsed:
                    results = []
                    for item in parsed["facts"]:
                        if isinstance(item, dict) and "key" in item and "value" in item:
                            results.append(
                                {
                                    "key": str(item["key"]).strip(),
                                    "value": str(item["value"]).strip(),
                                    "confidence": 0.85,
                                }
                            )
                    return results
    except Exception as e:
        logger.debug(f"LLM fact extraction skipped or failed: {e}")

    return []


async def process_and_store_candidate_facts(
    conn: aiosqlite.Connection, text: str
) -> list[dict[str, Any]]:
    """
    Extract facts from user message and store them with status 'pending'.
    Only saves if not already approved with the same value.
    """
    if not text or len(text.strip()) < 5:
        return []

    # 1. Try heuristic extraction first
    candidates = extract_heuristic_facts(text)

    # 2. If heuristic found nothing, attempt LLM extraction
    if not candidates:
        candidates = await extract_facts_with_llm(text)

    if not candidates:
        return []

    stored_facts = []
    # Fetch existing facts to avoid overwriting approved ones
    existing_facts = await repository.list_profile_facts(conn)
    existing_map = {f["key"].lower(): f for f in existing_facts}

    for cand in candidates:
        key = cand["key"].strip()
        val = cand["value"].strip()
        if not key or not val:
            continue

        existing = existing_map.get(key.lower())
        if existing:
            # If already approved with the same value, do not duplicate or downgrade
            if existing["status"] == "approved" and existing["value"] == val:
                continue
            # If rejected with the same value, do not re-propose
            if existing["status"] == "rejected" and existing["value"] == val:
                continue

        # Save as pending for owner approval
        fact = await repository.create_profile_fact(
            conn,
            key=key,
            value=val,
            status="pending",
            confidence=cand.get("confidence", 0.8),
        )
        stored_facts.append(fact)

    return stored_facts
