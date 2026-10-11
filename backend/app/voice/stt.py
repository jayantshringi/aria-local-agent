"""Speech-to-Text (STT) client powered by local faster-whisper."""

import asyncio
import io
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.voice.audio_utils import validate_wav_bytes

logger = logging.getLogger("aria.voice.stt")


class WhisperSTTClient:
    """Local Speech-to-Text client using faster-whisper (offline INT8 CTranslate2)."""

    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        download_root: Path | None = None,
    ):
        settings = get_settings()
        self.model_size = model_size or settings.whisper_model
        self.device = device or settings.whisper_device
        self.compute_type = compute_type or settings.whisper_compute_type
        self.download_root = download_root or settings.whisper_dir_path
        self._model: Any = None
        self._lock = asyncio.Lock()

    def _get_or_load_model(self) -> Any:
        """Synchronously load the faster-whisper model into memory."""
        if self._model is not None:
            return self._model

        from faster_whisper import WhisperModel

        logger.info(
            f"Loading faster-whisper model '{self.model_size}' "
            f"(device={self.device}, compute_type={self.compute_type}, dir={self.download_root})..."
        )
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            download_root=str(self.download_root),
        )
        return self._model

    def _transcribe_sync(
        self,
        audio_stream: io.BytesIO,
        language: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Run CPU/INT8 transcription synchronously."""
        model = self._get_or_load_model()
        # faster-whisper transcribe supports file-like binary stream
        segments_generator, info = model.transcribe(
            audio_stream,
            beam_size=5,
            language=language,
            vad_filter=True,
        )

        segment_texts = []
        detailed_segments = []
        for s in segments_generator:
            segment_texts.append(s.text.strip())
            detailed_segments.append(
                {
                    "start": s.start,
                    "end": s.end,
                    "text": s.text.strip(),
                }
            )

        full_text = " ".join(segment_texts).strip()
        metadata = {
            "language": info.language,
            "language_probability": float(info.language_probability),
            "duration": float(info.duration),
            "segments": detailed_segments,
        }
        return full_text, metadata

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Transcribe audio WAV byte stream asynchronously without blocking event loop."""
        # Validate WAV structure
        info = validate_wav_bytes(audio_bytes)
        logger.debug(
            f"Transcribing audio: {info.duration_seconds:.2f}s, {info.sample_rate}Hz, {info.channels}ch"
        )

        stream = io.BytesIO(audio_bytes)
        async with self._lock:
            return await asyncio.to_thread(self._transcribe_sync, stream, language)


@lru_cache
def get_stt_client() -> WhisperSTTClient:
    """Return singleton cached instance of WhisperSTTClient."""
    return WhisperSTTClient()
