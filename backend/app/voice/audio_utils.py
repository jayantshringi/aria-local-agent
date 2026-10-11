"""Audio processing and WAV validation utilities for aria-local-agent voice layer."""

import io
import logging
import wave
from typing import NamedTuple

logger = logging.getLogger("aria.voice.audio_utils")


class AudioInfo(NamedTuple):
    sample_rate: int
    channels: int
    sample_width: int
    num_frames: int
    duration_seconds: float


def validate_wav_bytes(audio_bytes: bytes) -> AudioInfo:
    """Validate WAV byte data and return format information.

    Raises:
        ValueError: If audio_bytes is empty, corrupted, or not a valid WAV format.
    """
    if not audio_bytes or len(audio_bytes) < 44:
        raise ValueError("Audio data is empty or too short to be a valid WAV file")

    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            num_frames = wav_file.getnframes()
            duration = num_frames / float(sample_rate) if sample_rate > 0 else 0.0

            return AudioInfo(
                sample_rate=sample_rate,
                channels=channels,
                sample_width=sample_width,
                num_frames=num_frames,
                duration_seconds=duration,
            )
    except Exception as exc:
        raise ValueError(f"Invalid WAV audio data: {exc}") from exc


def is_valid_wav(audio_bytes: bytes) -> bool:
    """Check if audio data is a readable WAV format without raising."""
    try:
        validate_wav_bytes(audio_bytes)
        return True
    except Exception:
        return False


def create_wav_bytes(
    pcm_data: bytes,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Wrap raw 16-bit linear PCM byte buffer into standard WAV container."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return buffer.getvalue()
