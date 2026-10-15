"""Streaming audio buffer and Voice Activity Detection for real-time speech streaming."""

import io
import math
import struct
import wave
from typing import Any

from app.voice.audio_utils import create_wav_bytes


class AudioStreamBuffer:
    """Manages an incoming stream of raw audio chunks with energy detection and WAV assembly."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
        silence_threshold_rms: float = 300.0,
        max_duration_seconds: float = 60.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.silence_threshold_rms = silence_threshold_rms
        self.max_duration_seconds = max_duration_seconds

        self._raw_pcm = bytearray()
        self._bytes_per_second = sample_rate * channels * sample_width
        self._max_bytes = int(self._bytes_per_second * max_duration_seconds)

    def append_chunk(self, chunk: bytes) -> dict[str, Any]:
        """Append incoming audio bytes (raw PCM or WAV) to the buffer."""
        if not chunk:
            return {"bytes_added": 0, "total_duration": self.duration_seconds, "is_speech": False}

        # If incoming chunk is already a complete WAV header, extract raw PCM payload
        if chunk.startswith(b"RIFF") and len(chunk) >= 44:
            try:
                with wave.open(io.BytesIO(chunk), "rb") as wf:
                    pcm_payload = wf.readframes(wf.getnframes())
            except Exception:
                pcm_payload = chunk[44:]
        else:
            pcm_payload = chunk

        # Guard against buffer overflow
        if len(self._raw_pcm) + len(pcm_payload) > self._max_bytes:
            # Drop older data or clamp
            overflow = (len(self._raw_pcm) + len(pcm_payload)) - self._max_bytes
            self._raw_pcm = self._raw_pcm[overflow:]

        self._raw_pcm.extend(pcm_payload)

        rms = self._calculate_rms(pcm_payload)
        is_speech = rms >= self.silence_threshold_rms

        return {
            "bytes_added": len(pcm_payload),
            "total_bytes": len(self._raw_pcm),
            "total_duration": self.duration_seconds,
            "rms": round(rms, 2),
            "is_speech": is_speech,
        }

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds of current buffered PCM."""
        if self._bytes_per_second <= 0:
            return 0.0
        return len(self._raw_pcm) / float(self._bytes_per_second)

    def to_wav_bytes(self) -> bytes:
        """Convert accumulated PCM buffer to standard 16kHz mono WAV bytes."""
        return create_wav_bytes(
            bytes(self._raw_pcm),
            sample_rate=self.sample_rate,
            channels=self.channels,
            sample_width=self.sample_width,
        )

    def clear(self) -> None:
        """Reset the buffer."""
        self._raw_pcm.clear()

    def _calculate_rms(self, pcm_bytes: bytes) -> float:
        """Compute root mean square energy of 16-bit linear PCM audio chunk."""
        num_samples = len(pcm_bytes) // 2
        if num_samples == 0:
            return 0.0

        fmt = f"<{num_samples}h"
        try:
            samples = struct.unpack(fmt, pcm_bytes[: num_samples * 2])
            sum_sq = sum(s * s for s in samples)
            return math.sqrt(sum_sq / num_samples)
        except Exception:
            return 0.0


__all__ = ["AudioStreamBuffer"]
