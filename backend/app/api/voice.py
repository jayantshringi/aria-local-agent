"""REST API routes for local speech-to-text (Whisper) and text-to-speech (Piper)."""

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field

from app.auth.security import get_current_device
from app.config import get_settings
from app.voice.audio_utils import is_valid_wav
from app.voice.stt import get_stt_client
from app.voice.tts import VoiceModelNotFoundError, get_tts_client

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


class SynthesizeRequest(BaseModel):
    text: str = Field(..., description="Text content to speak")


class TranscribeResponse(BaseModel):
    text: str
    metadata: dict[str, Any]


@router.get("/status")
async def voice_status(
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Check availability of local STT and TTS models."""
    settings = get_settings()
    stt = get_stt_client()
    tts = get_tts_client()
    return {
        "stt_available": True,
        "stt_model": stt.model_size,
        "tts_available": tts.is_model_available(),
        "tts_model": tts.voice_model_name,
        "language": settings.aria_language,
    }


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile = File(..., description="16kHz 16-bit mono PCM WAV audio recording"),
    language: str | None = Query(
        default=None, description="Optional language override (e.g. 'en')"
    ),
    _: dict[str, Any] = Depends(get_current_device),
) -> dict[str, Any]:
    """Transcribe recorded speech using local faster-whisper without external network calls."""
    try:
        audio_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded audio file: {exc}",
        ) from exc

    if not audio_bytes or len(audio_bytes) < 44 or not is_valid_wav(audio_bytes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty or not a valid WAV audio file",
        )

    stt = get_stt_client()
    try:
        text, metadata = await stt.transcribe(audio_bytes, language=language)
        return {"text": text, "metadata": metadata}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {exc}",
        ) from exc


@router.post("/synthesize")
async def synthesize_speech(
    req: SynthesizeRequest,
    _: dict[str, Any] = Depends(get_current_device),
) -> Response:
    """Synthesize text into WAV speech using local Piper ONNX neural voices."""
    if not req.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text to synthesize cannot be empty",
        )

    tts = get_tts_client()
    try:
        wav_bytes = await tts.synthesize(req.text)
        return Response(content=wav_bytes, media_type="audio/wav")
    except VoiceModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech synthesis failed: {exc}",
        ) from exc
