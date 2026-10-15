"""Text-to-Speech streaming synthesis pipeline using Piper neural voice."""

import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

from app.voice.tts import PiperTTSClient, get_tts_client

logger = logging.getLogger("aria.audio.tts")


class StreamingTTSHandler:
    """Asynchronous TTS pipeline supporting low-latency sentence-level speech streaming."""

    def __init__(self, client: PiperTTSClient | None = None) -> None:
        self.client = client or get_tts_client()

    async def synthesize_full(self, text: str) -> bytes:
        """Synthesize entire text into single complete WAV buffer."""
        cleaned = text.strip()
        if not cleaned:
            return b""
        return await self.client.synthesize(cleaned)

    async def synthesize_stream(
        self,
        text: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream synthesized audio sentence-by-sentence for minimal latency playback."""
        sentences = self._split_sentences(text)
        if not sentences:
            return

        for idx, sentence in enumerate(sentences):
            try:
                wav_chunk = await self.client.synthesize(sentence)
                yield {
                    "index": idx,
                    "total_sentences": len(sentences),
                    "sentence": sentence,
                    "audio_bytes": wav_chunk,
                    "is_last": idx == len(sentences) - 1,
                }
            except Exception as exc:
                logger.warning(f"Failed to synthesize sentence {idx} ('{sentence}'): {exc}")
                continue

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into spoken sentences at punctuation boundaries."""
        # Split on ., !, ?, ;, or newlines
        parts = re.split(r"(?<=[.!?;\n])\s+", text.strip())
        sentences = [p.strip() for p in parts if p.strip()]
        return sentences if sentences else [text.strip()]


__all__ = ["StreamingTTSHandler"]
