"""Speech-to-Text streaming pipeline for faster-whisper."""

import logging
from typing import Any

from app.voice.audio_utils import is_valid_wav
from app.voice.stt import WhisperSTTClient, get_stt_client

logger = logging.getLogger("aria.audio.stt")


class StreamingSTTHandler:
    """Asynchronous STT pipeline managing transcription from streaming audio buffers."""

    def __init__(self, client: WhisperSTTClient | None = None) -> None:
        self.client = client or get_stt_client()

    async def transcribe_wav(
        self,
        wav_bytes: bytes,
        language: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Transcribe completed WAV audio bytes using faster-whisper without cloud calls."""
        if not wav_bytes or len(wav_bytes) < 44 or not is_valid_wav(wav_bytes):
            return "", {"error": "Invalid or empty WAV audio data"}

        try:
            return await self.client.transcribe(wav_bytes, language=language)
        except Exception as exc:
            logger.error(f"STT transcription failed: {exc}")
            return "", {"error": str(exc)}


__all__ = ["StreamingSTTHandler"]
