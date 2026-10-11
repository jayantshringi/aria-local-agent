"""Text-to-Speech (TTS) client powered by local Piper ONNX voices."""

import asyncio
import io
import logging
import wave
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.voice.audio_utils import create_wav_bytes

logger = logging.getLogger("aria.voice.tts")


class VoiceModelNotFoundError(FileNotFoundError):
    """Raised when the specified Piper ONNX voice model is not downloaded locally."""

    pass


class PiperTTSClient:
    """Local Text-to-Speech client using Piper ONNX neural voices."""

    def __init__(
        self,
        voice_model: str | None = None,
        voice_dir: Path | None = None,
        use_cuda: bool = False,
    ):
        settings = get_settings()
        self.voice_model_name = voice_model or settings.piper_voice_model
        self.voice_dir = voice_dir or settings.piper_dir_path
        self.use_cuda = use_cuda
        self._voice: Any = None
        self._lock = asyncio.Lock()

    def get_model_paths(self) -> tuple[Path, Path]:
        """Resolve expected .onnx and .onnx.json paths for the configured voice."""
        model_name = self.voice_model_name
        # If model_name is already a path to .onnx file
        if model_name.endswith(".onnx"):
            onnx_path = Path(model_name)
            if not onnx_path.is_absolute():
                onnx_path = self.voice_dir / onnx_path
            json_path = Path(f"{onnx_path}.json")
            return onnx_path, json_path

        onnx_path = self.voice_dir / f"{model_name}.onnx"
        json_path = self.voice_dir / f"{model_name}.onnx.json"
        return onnx_path, json_path

    def is_model_available(self) -> bool:
        """Check if local ONNX and JSON files exist."""
        onnx_path, json_path = self.get_model_paths()
        return onnx_path.is_file() and json_path.is_file()

    def _get_or_load_voice(self) -> Any:
        """Load PiperVoice model into memory."""
        if self._voice is not None:
            return self._voice

        onnx_path, json_path = self.get_model_paths()
        if not onnx_path.is_file() or not json_path.is_file():
            raise VoiceModelNotFoundError(
                f"Piper voice model '{self.voice_model_name}' not found locally at {onnx_path}. "
                f"Please download '{onnx_path.name}' and '{json_path.name}' into '{self.voice_dir}'."
            )

        from piper import PiperVoice

        logger.info(f"Loading Piper TTS voice from {onnx_path}...")
        self._voice = PiperVoice.load(
            model_path=str(onnx_path),
            config_path=str(json_path),
            use_cuda=self.use_cuda,
        )
        return self._voice

    def _synthesize_sync(self, text: str) -> bytes:
        """Synthesize text to WAV bytes synchronously."""
        clean_text = text.strip()
        if not clean_text:
            # Return 0.25s of silence
            return create_wav_bytes(b"\x00\x00" * 4000, sample_rate=16000)

        voice = self._get_or_load_voice()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            voice.synthesize_wav(clean_text, wav_file)
        return buffer.getvalue()

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text into WAV byte buffer asynchronously without blocking the event loop."""
        async with self._lock:
            return await asyncio.to_thread(self._synthesize_sync, text)


@lru_cache
def get_tts_client() -> PiperTTSClient:
    """Return singleton cached instance of PiperTTSClient."""
    return PiperTTSClient()
