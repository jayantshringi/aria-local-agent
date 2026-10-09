"""WebSocket endpoint for real-time token streaming from Ollama."""

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth.security import verify_device_token
from app.db import repository
from app.db.connection import get_database
from app.llm.ollama_client import OllamaClient, OllamaConnectionError, OllamaError
from app.llm.persona import load_persona

logger = logging.getLogger("aria.chat_ws")
router = APIRouter(tags=["chat"])


async def _authenticate_websocket(websocket: WebSocket) -> dict[str, Any] | None:
    """Authenticate websocket connection via query parameter or headers."""
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


@router.websocket("/ws/chat")
async def chat_websocket_endpoint(websocket: WebSocket) -> None:
    """
    Streaming chat WebSocket endpoint.
    Manages authentication, immediate message persistence, persona loading,
    and token-by-token streaming from local Ollama.
    """
    await websocket.accept()

    device = await _authenticate_websocket(websocket)
    if not device:
        await websocket.send_text(
            json.dumps({"type": "error", "error": "Unauthorized: invalid or missing device token"})
        )
        await websocket.close(code=4001)
        return

    # Acknowledge connection
    await websocket.send_text(
        json.dumps(
            {
                "type": "connected",
                "device": {"id": device["id"], "name": device["name"]},
            }
        )
    )

    ollama_client = OllamaClient()
    db = get_database()

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                event = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "error": "Invalid JSON payload"})
                )
                continue

            event_type = event.get("type")
            if event_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            if event_type != "message":
                continue

            content = (event.get("content") or "").strip()
            if not content:
                continue

            session_id = event.get("session_id")
            model_override = event.get("model")

            async with db.get_connection() as conn:
                # 1. Resolve or create session
                session = None
                if session_id:
                    session = await repository.get_session(conn, session_id)

                if not session:
                    # Generate short title from first question
                    snippet = content.split("\n")[0][:32].strip()
                    title = snippet if snippet else "New Chat"
                    session = await repository.create_session(
                        conn, title=title, device_id=device["id"]
                    )
                    session_id = session["id"]

                # 2. Immediately persist user message
                user_msg = await repository.create_message(
                    conn,
                    session_id=session_id,
                    role="user",
                    content=content,
                )

                # Send message confirmation
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "message_saved",
                            "session_id": session_id,
                            "message": user_msg,
                        }
                    )
                )

                # 3. Assemble prompt context (persona + recent conversation history)
                system_persona = load_persona()
                recent_messages = await repository.list_messages(
                    conn, session_id=session_id, limit=20
                )

                prompt_messages: list[dict[str, str]] = [
                    {"role": "system", "content": system_persona}
                ]
                for msg in recent_messages:
                    prompt_messages.append(
                        {
                            "role": msg["role"],
                            "content": msg["content"],
                        }
                    )

            # 4. Stream tokens from Ollama
            accumulated_content = []
            tokens_generated = 0

            try:
                async for chunk in ollama_client.stream_chat(prompt_messages, model=model_override):
                    if chunk["type"] == "delta":
                        delta_text = chunk["content"]
                        accumulated_content.append(delta_text)
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "token",
                                    "session_id": session_id,
                                    "delta": delta_text,
                                }
                            )
                        )
                    elif chunk["type"] == "done":
                        tokens_generated = chunk.get("tokens", 0)

                full_assistant_reply = "".join(accumulated_content)

                # 5. Immediately persist completed assistant message
                async with db.get_connection() as conn:
                    assistant_msg = await repository.create_message(
                        conn,
                        session_id=session_id,
                        role="assistant",
                        content=full_assistant_reply,
                        tokens=tokens_generated,
                    )

                # Notify client that generation is finished
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "done",
                            "session_id": session_id,
                            "message": assistant_msg,
                        }
                    )
                )

            except OllamaConnectionError as conn_err:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "session_id": session_id,
                            "error": str(conn_err),
                        }
                    )
                )
            except OllamaError as ollama_err:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "session_id": session_id,
                            "error": f"Ollama error: {ollama_err}",
                        }
                    )
                )
            except Exception as exc:
                logger.exception("Unexpected error in chat streaming")
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "session_id": session_id,
                            "error": f"Streaming failure: {str(exc)}",
                        }
                    )
                )

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: device {device.get('id')}")
