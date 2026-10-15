"""Unit and integration tests for the real-time audio streaming pipeline."""

import struct
from unittest.mock import AsyncMock

import pytest

from app.voice.audio_utils import is_valid_wav, validate_wav_bytes
from audio.buffer import AudioStreamBuffer
from audio.stt import StreamingSTTHandler
from audio.tts import StreamingTTSHandler


def test_audio_stream_buffer():
    buffer = AudioStreamBuffer(sample_rate=16000, channels=1, sample_width=2)
    assert buffer.duration_seconds == 0.0

    # Create 0.1 second of 16-bit linear PCM silence
    samples = 1600
    silence_pcm = b"\x00\x00" * samples
    stat1 = buffer.append_chunk(silence_pcm)
    assert stat1["bytes_added"] == len(silence_pcm)
    assert stat1["is_speech"] is False
    assert round(buffer.duration_seconds, 1) == 0.1

    # Create 0.1 second of tone (audible amplitude)
    loud_pcm = struct.pack(f"<{samples}h", *([8000] * samples))
    stat2 = buffer.append_chunk(loud_pcm)
    assert stat2["is_speech"] is True
    assert round(buffer.duration_seconds, 1) == 0.2

    # Verify generated WAV
    wav_data = buffer.to_wav_bytes()
    assert is_valid_wav(wav_data) is True
    info = validate_wav_bytes(wav_data)
    assert info.sample_rate == 16000
    assert info.channels == 1

    # Clear buffer
    buffer.clear()
    assert buffer.duration_seconds == 0.0


def test_streaming_tts_sentence_splitting():
    tts = StreamingTTSHandler()
    text = "Hello world! This is Aria, your personal OS. How can I assist you today?"
    sentences = tts._split_sentences(text)
    assert len(sentences) == 3
    assert sentences[0] == "Hello world!"
    assert sentences[1] == "This is Aria, your personal OS."
    assert sentences[2] == "How can I assist you today?"


@pytest.mark.asyncio
async def test_streaming_tts_synthesis_stream():
    # Mock underlying client to avoid requiring full Piper model download in CI
    mock_client = AsyncMock()
    mock_client.synthesize.return_value = b"RIFF....WAVEfmt ...."
    tts = StreamingTTSHandler(client=mock_client)

    chunks = []
    async for chunk in tts.synthesize_stream("First sentence. Second sentence."):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert chunks[0]["index"] == 0
    assert chunks[0]["is_last"] is False
    assert chunks[1]["index"] == 1
    assert chunks[1]["is_last"] is True


@pytest.mark.asyncio
async def test_streaming_stt_handler():
    stt = StreamingSTTHandler()

    # Empty or invalid audio returns error safely
    text, meta = await stt.transcribe_wav(b"")
    assert text == ""
    assert "error" in meta
