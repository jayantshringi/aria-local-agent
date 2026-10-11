"""Unit and integration tests for Phase 5 Voice layer (STT, TTS, Audio utils)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.voice.audio_utils import create_wav_bytes, is_valid_wav, validate_wav_bytes
from app.voice.stt import WhisperSTTClient
from app.voice.tts import PiperTTSClient, VoiceModelNotFoundError


@pytest.fixture
async def auth_headers(async_client: AsyncClient) -> dict[str, str]:
    """Helper to login and obtain valid auth headers."""
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"password": "TestPassword123", "device_name": "TestDevice"},
    )
    assert resp.status_code == 200
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_validate_wav_bytes():
    """Verify in-memory WAV generation and format validation."""
    # 1 second of 16kHz 16-bit mono PCM (32,000 bytes)
    raw_pcm = b"\x00\x00" * 16000
    wav_bytes = create_wav_bytes(raw_pcm, sample_rate=16000, channels=1, sample_width=2)

    assert len(wav_bytes) == 32044
    assert is_valid_wav(wav_bytes) is True

    info = validate_wav_bytes(wav_bytes)
    assert info.sample_rate == 16000
    assert info.channels == 1
    assert info.sample_width == 2
    assert info.num_frames == 16000
    assert abs(info.duration_seconds - 1.0) < 0.01


def test_invalid_wav_bytes():
    """Verify corrupted or truncated audio data raises ValueError."""
    assert is_valid_wav(b"") is False
    assert is_valid_wav(b"not a wav file") is False

    with pytest.raises(ValueError, match="empty or too short"):
        validate_wav_bytes(b"short")

    with pytest.raises(ValueError, match="Invalid WAV audio"):
        validate_wav_bytes(b"RIFF" + b"\x00" * 40)


@pytest.mark.asyncio
async def test_voice_status_endpoint(async_client: AsyncClient, auth_headers: dict[str, str]):
    """Verify GET /api/v1/voice/status returns model info."""
    resp = await async_client.get("/api/v1/voice/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["stt_available"] is True
    assert "stt_model" in data
    assert "tts_available" in data
    assert "language" in data


@pytest.mark.asyncio
async def test_transcribe_valid_audio(async_client: AsyncClient, auth_headers: dict[str, str]):
    """Verify POST /api/v1/voice/transcribe with mocked STT client."""
    raw_pcm = b"\x00\x00" * 8000  # 0.5 sec
    wav_bytes = create_wav_bytes(raw_pcm, sample_rate=16000)

    mock_text = "remind me at 6 PM to call Ahmed"
    mock_meta = {
        "language": "en",
        "language_probability": 0.99,
        "duration": 0.5,
        "segments": [{"start": 0.0, "end": 0.5, "text": mock_text}],
    }

    with patch.object(WhisperSTTClient, "transcribe", new_callable=AsyncMock) as mock_transcribe:
        mock_transcribe.return_value = (mock_text, mock_meta)

        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
        resp = await async_client.post(
            "/api/v1/voice/transcribe?language=en",
            headers=auth_headers,
            files=files,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == mock_text
        assert data["metadata"]["language"] == "en"
        mock_transcribe.assert_called_once()


@pytest.mark.asyncio
async def test_transcribe_invalid_audio_returns_400(
    async_client: AsyncClient, auth_headers: dict[str, str]
):
    """Verify uploading non-WAV data returns HTTP 400."""
    files = {"file": ("corrupted.wav", b"invalid-bytes", "audio/wav")}
    resp = await async_client.post(
        "/api/v1/voice/transcribe",
        headers=auth_headers,
        files=files,
    )
    assert resp.status_code == 400
    assert "not a valid WAV" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_synthesize_endpoint_missing_model(
    async_client: AsyncClient, auth_headers: dict[str, str]
):
    """Verify HTTP 503 returned when Piper voice model is not found locally."""
    with patch.object(PiperTTSClient, "is_model_available", return_value=False):
        with patch.object(
            PiperTTSClient,
            "synthesize",
            side_effect=VoiceModelNotFoundError("Model not downloaded"),
        ):
            resp = await async_client.post(
                "/api/v1/voice/synthesize",
                headers=auth_headers,
                json={"text": "Hello owner"},
            )
            assert resp.status_code == 503
            assert "Model not downloaded" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_synthesize_endpoint_success(async_client: AsyncClient, auth_headers: dict[str, str]):
    """Verify successful speech synthesis returns audio/wav."""
    dummy_wav = create_wav_bytes(b"\x00\x00" * 4000)

    with patch.object(PiperTTSClient, "synthesize", new_callable=AsyncMock) as mock_synth:
        mock_synth.return_value = dummy_wav

        resp = await async_client.post(
            "/api/v1/voice/synthesize",
            headers=auth_headers,
            json={"text": "Good morning! You have 2 reminders today."},
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"
        assert resp.content == dummy_wav
