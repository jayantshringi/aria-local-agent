"""Bidirectional WebSocket endpoint for real-time audio chunk streaming, STT, and TTS."""

import base64
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth.security import verify_device_token
from app.db.connection import get_database
from audio.buffer import AudioStreamBuffer
from audio.stt import StreamingSTTHandler
from audio.tts import StreamingTTSHandler
from core.loop import OPECAgentLoop

logger = logging.getLogger("aria.audio.ws")
router = APIRouter(tags=["audio"])


async def _authenticate_ws(websocket: WebSocket) -> dict[str, Any] | None:
    """Authenticate WebSocket connection using device token."""
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif websocket.headers.get("x-device-token"):
            token = websocket.headers.get("x-device-token")

    if not token:
        return None

    db = get_database()
    async with db.get_connection() as conn:
        return await verify_device_token(conn, token)


@router.websocket("/ws/audio")
async def audio_websocket_endpoint(websocket: WebSocket) -> None:
    """
    Real-time streaming audio WebSocket.
    Supports continuous audio chunk ingestion, Voice Activity Detection (VAD),
    faster-whisper transcription, end-to-end OPEC agent execution, and Piper TTS streaming.
    """
    await websocket.accept()

    device = await _authenticate_ws(websocket)
    if not device:
        await websocket.send_text(
            json.dumps({"type": "error", "error": "Unauthorized: invalid device token"})
        )
        await websocket.close(code=4001)
        return

    await websocket.send_text(
        json.dumps(
            {
                "type": "audio_connected",
                "device": {"id": device["id"], "name": device["name"]},
                "supported_sample_rate": 16000,
            }
        )
    )

    audio_buffer = AudioStreamBuffer()
    stt_handler = StreamingSTTHandler()
    tts_handler = StreamingTTSHandler()
    agent_loop = OPECAgentLoop()

    try:
        while True:
            # Handle either binary audio frames or JSON control events
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                chunk_bytes = message["bytes"]
                stat = audio_buffer.append_chunk(chunk_bytes)
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "vad_status",
                            "is_speech": stat["is_speech"],
                            "rms": stat["rms"],
                            "duration": stat["total_duration"],
                        }
                    )
                )
                continue

            if "text" not in message or not message["text"]:
                continue

            try:
                event = json.loads(message["text"])
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "error": "Invalid JSON frame"})
                )
                continue

            event_type = event.get("type")

            if event_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            if event_type == "audio_chunk":
                raw_b64 = event.get("data", "")
                if raw_b64:
                    pcm_bytes = base64.b64decode(raw_b64)
                    stat = audio_buffer.append_chunk(pcm_bytes)
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "vad_status",
                                "is_speech": stat["is_speech"],
                                "rms": stat["rms"],
                                "duration": stat["total_duration"],
                            }
                        )
                    )
                continue

            if event_type == "clear_buffer":
                audio_buffer.clear()
                await websocket.send_text(json.dumps({"type": "buffer_cleared"}))
                continue

            if event_type == "speech_end" or event_type == "transcribe_now":
                wav_bytes = audio_buffer.to_wav_bytes()
                audio_buffer.clear()
                text, meta = await stt_handler.transcribe_wav(wav_bytes)
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "transcription",
                            "text": text,
                            "metadata": meta,
                        }
                    )
                )
                continue

            if event_type == "voice_chat":
                # 1. Transcribe current buffer
                wav_bytes = audio_buffer.to_wav_bytes()
                audio_buffer.clear()
                user_transcript, meta = await stt_handler.transcribe_wav(wav_bytes)

                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "transcription_final",
                            "text": user_transcript,
                            "metadata": meta,
                        }
                    )
                )

                if not user_transcript.strip():
                    await websocket.send_text(
                        json.dumps(
                            {"type": "error", "error": "No speech detected in audio stream."}
                        )
                    )
                    continue

                # 2. Pipe transcript into OPEC Agent Loop with live event streaming
                session_id = event.get("session_id")

                async def forward_agent_event(ev: dict[str, Any]) -> None:
                    await websocket.send_text(json.dumps({"type": "agent_event", "event": ev}))

                loop_result = await agent_loop.run(
                    user_input=user_transcript,
                    session_id=session_id,
                    device_id=device["id"],
                    event_callback=forward_agent_event,
                )

                final_reply = loop_result.get("final_answer", "")
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "agent_reply",
                            "text": final_reply,
                            "success": loop_result["success"],
                        }
                    )
                )

                # 3. Stream synthesized voice response sentence-by-sentence
                if final_reply:
                    async for chunk in tts_handler.synthesize_stream(final_reply):
                        b64_audio = base64.b64encode(chunk["audio_bytes"]).decode("ascii")
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "audio_reply_chunk",
                                    "index": chunk["index"],
                                    "sentence": chunk["sentence"],
                                    "audio_base64": b64_audio,
                                    "is_last": chunk["is_last"],
                                }
                            )
                        )

                await websocket.send_text(json.dumps({"type": "voice_turn_done"}))
                continue

            if event_type == "speak_text":
                text = event.get("text", "").strip()
                if not text:
                    continue
                async for chunk in tts_handler.synthesize_stream(text):
                    b64_audio = base64.b64encode(chunk["audio_bytes"]).decode("ascii")
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "audio_reply_chunk",
                                "index": chunk["index"],
                                "sentence": chunk["sentence"],
                                "audio_base64": b64_audio,
                                "is_last": chunk["is_last"],
                            }
                        )
                    )
                await websocket.send_text(json.dumps({"type": "speech_done"}))
                continue

    except WebSocketDisconnect:
        logger.info(f"Audio WebSocket disconnected for device {device.get('id')}")
    except Exception as exc:
        logger.exception(f"Unexpected error in audio WebSocket: {exc}")


__all__ = ["router", "audio_websocket_endpoint"]
