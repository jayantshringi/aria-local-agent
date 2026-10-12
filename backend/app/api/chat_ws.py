"""WebSocket endpoint for real-time token streaming from Ollama."""

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.sync_hub import sync_hub
from app.auth.security import verify_device_token
from app.config import get_settings
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
    Manages authentication, multi-device synchronization, immediate message persistence,
    persona loading, and token-by-token streaming from local Ollama.
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

    # Register client connection in multi-device sync hub
    client = await sync_hub.register(websocket, device["id"], device["name"])

    try:
        # Update last seen timestamp for the device
        async with db.get_connection() as conn:
            await repository.update_device_last_seen(conn, device["id"])

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

            if event_type == "select_session":
                selected_id = event.get("session_id")
                sync_hub.set_client_session(client, selected_id)
                continue

            if event_type == "action_approve":
                action_id = event.get("action_id")
                from app.agent.loop import approve_and_execute_action

                res = await approve_and_execute_action(action_id, resolved_by=device["name"])
                await websocket.send_text(json.dumps({"type": "action_result", "result": res}))
                continue

            if event_type == "action_reject":
                action_id = event.get("action_id")
                from app.agent.loop import reject_pending_action

                res = await reject_pending_action(action_id, resolved_by=device["name"])
                await websocket.send_text(json.dumps({"type": "action_result", "result": res}))
                continue

            if event_type == "kill":
                from app.agent.kill_switch import kill_switch

                killed = await kill_switch.trigger()
                await websocket.send_text(
                    json.dumps({"type": "agent_killed", "killed_actions": killed})
                )
                continue

            if event_type == "execute_tool":
                tool_name = event.get("tool")
                tool_args = event.get("args") or {}
                tool_session_id = event.get("session_id")
                from app.agent.loop import dispatch_tool_call

                res = await dispatch_tool_call(
                    tool_name, tool_args, session_id=tool_session_id, device_id=device["id"]
                )
                await websocket.send_text(json.dumps({"type": "tool_dispatched", "result": res}))
                continue

            if event_type != "message":
                continue

            content = (event.get("content") or "").strip()
            if not content:
                continue

            session_id = event.get("session_id")
            model_override = event.get("model")

            async with db.get_connection() as conn:
                # Keep last seen updated on activity
                await repository.update_device_last_seen(conn, device["id"])

                # Resolve active model from SQLite settings (Phase 6 model switcher)
                from app.system.models import get_active_chat_model

                active_configured_model = await get_active_chat_model(conn)
                effective_model = model_override or active_configured_model

                # 1. Resolve or create session
                session = None
                created_new_session = False
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
                    created_new_session = True

                sync_hub.set_client_session(client, session_id)

                # Broadcast new session creation across other devices
                if created_new_session:
                    await sync_hub.broadcast_all(
                        {"type": "session_created", "session": session}, exclude=client
                    )

                # 2. Immediately persist user message
                user_msg = await repository.create_message(
                    conn,
                    session_id=session_id,
                    role="user",
                    content=content,
                )

                # Send message confirmation to sender
                msg_saved_payload = {
                    "type": "message_saved",
                    "session_id": session_id,
                    "message": user_msg,
                }
                await websocket.send_text(json.dumps(msg_saved_payload))

                # Real-time multi-device sync:
                # mirror user message to all other connected devices viewing this session
                await sync_hub.broadcast_session(session_id, msg_saved_payload, exclude=client)

                # 3. Memory Retrieval & Profile Facts (Phase 2) + Tool Registry (Phase 4)
                system_persona = load_persona()

                # Fetch approved profile facts (hard rule: only approved facts enter prompt)
                from app.agent.registry import tool_registry
                from app.memory.profile import format_facts_for_prompt, get_approved_facts
                from app.memory.retrieval import format_memories_for_prompt, hybrid_search

                approved_facts = await get_approved_facts(conn)
                facts_context = format_facts_for_prompt(approved_facts)

                # Hybrid search across past memories
                retrieved_memories = await hybrid_search(
                    conn, query=content, limit=5, token_budget=800
                )
                memories_context = format_memories_for_prompt(retrieved_memories)

                # Format available tools
                tools_list = tool_registry.list_tools()
                tools_context = ""
                if tools_list:
                    tools_lines = [
                        "## Available Tools",
                        "You have access to the following local tools:",
                    ]
                    for t in tools_list:
                        props = t.parameters.get("properties", {}) if t.parameters else {}
                        params_desc = ", ".join(
                            f"{k}: {v.get('type', 'any')}" for k, v in props.items()
                        )
                        tools_lines.append(
                            f"- {t.name}({params_desc}) [{t.risk_level.value} risk]: {t.description}"
                        )
                    tools_lines.append("")
                    tools_lines.append(
                        "To use a tool, output a single JSON block formatted strictly as:\n"
                        "```tool_call\n"
                        '{"tool": "tool_name", "args": {"param1": "value1"}}\n'
                        "```\n"
                        "Never execute commands or read files outside permitted folders. "
                        "Medium and high risk tools require explicit owner approval."
                    )
                    tools_context = "\n".join(tools_lines)

                system_sections = [system_persona]
                settings = get_settings()
                if settings.aria_language and settings.aria_language != "en":
                    system_sections.append(
                        f"## Language Setting\nThe owner's configured assistant language is '{settings.aria_language}'. "
                        "Respond primarily in this language unless the user asks otherwise."
                    )
                if facts_context:
                    system_sections.append(facts_context)
                if memories_context:
                    system_sections.append(memories_context)
                if tools_context:
                    system_sections.append(tools_context)
                full_system_prompt = "\n\n".join(system_sections)

                recent_messages = await repository.list_messages(
                    conn, session_id=session_id, limit=30
                )

                # Context-window management (Phase 6): prune messages to prevent context overflow
                from app.llm.context import ContextWindowManager, estimate_tokens

                context_mgr = ContextWindowManager(max_context_tokens=settings.max_context_tokens)
                sys_tokens = estimate_tokens(full_system_prompt)
                pruned_messages = context_mgr.prune_messages(
                    recent_messages, system_overhead=sys_tokens
                )

                prompt_messages: list[dict[str, str]] = [
                    {"role": "system", "content": full_system_prompt}
                ]
                for msg in pruned_messages:
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
                async for chunk in ollama_client.stream_chat(
                    prompt_messages, model=effective_model
                ):
                    if chunk["type"] == "delta":
                        delta_text = chunk["content"]
                        accumulated_content.append(delta_text)
                        token_payload = {
                            "type": "token",
                            "session_id": session_id,
                            "delta": delta_text,
                        }
                        await websocket.send_text(json.dumps(token_payload))

                        # Mirror streaming tokens to other devices viewing this session
                        await sync_hub.broadcast_session(session_id, token_payload, exclude=client)
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

                # Notify sender that generation is finished
                done_payload = {
                    "type": "done",
                    "session_id": session_id,
                    "message": assistant_msg,
                }
                await websocket.send_text(json.dumps(done_payload))

                # Real-time multi-device sync: notify other devices that message is done
                await sync_hub.broadcast_session(session_id, done_payload, exclude=client)
                await sync_hub.broadcast_all(
                    {
                        "type": "session_updated",
                        "session": {"id": session_id, "updated_at": assistant_msg["created_at"]},
                    },
                    exclude=client,
                )

                # 5b. Autonomous Tool Dispatch (Phase 4)
                import re

                tool_match = re.search(
                    r"```tool_call\s*(\{.*?\})\s*```", full_assistant_reply, re.DOTALL
                )
                if tool_match:
                    try:
                        tool_data = json.loads(tool_match.group(1))
                        tool_name = tool_data.get("tool")
                        tool_args = tool_data.get("args") or {}
                        if tool_name:
                            from app.agent.loop import dispatch_tool_call

                            tool_res = await dispatch_tool_call(
                                tool_name,
                                tool_args,
                                session_id=session_id,
                                device_id=device["id"],
                            )
                            tool_status_payload = {
                                "type": "tool_dispatched",
                                "session_id": session_id,
                                "tool": tool_name,
                                "result": tool_res,
                            }
                            await websocket.send_text(json.dumps(tool_status_payload))
                            await sync_hub.broadcast_session(
                                session_id, tool_status_payload, exclude=client
                            )
                    except Exception as tool_parse_err:
                        logger.warning(
                            f"Failed to parse or dispatch model tool call: {tool_parse_err}"
                        )

                # 6. Post-generation memory indexing & background fact extraction (Phase 2)
                try:
                    from app.memory.embeddings import EmbeddingClient
                    from app.memory.extractor import process_and_store_candidate_facts
                    from app.memory.summarizer import summarize_session

                    embed_client = EmbeddingClient()
                    async with db.get_connection() as conn:
                        # Index user message vector
                        user_vec = await embed_client.get_embedding(content)
                        await repository.create_memory_chunk(
                            conn,
                            source_type="message",
                            source_id=user_msg["id"],
                            text=content,
                            embedding=user_vec,
                        )

                        # Index assistant message vector if reply non-empty
                        if full_assistant_reply.strip():
                            asst_vec = await embed_client.get_embedding(full_assistant_reply)
                            await repository.create_memory_chunk(
                                conn,
                                source_type="message",
                                source_id=assistant_msg["id"],
                                text=full_assistant_reply,
                                embedding=asst_vec,
                            )

                        # Extract candidate profile facts into 'pending'
                        await process_and_store_candidate_facts(conn, content)

                        # Update session summary
                        await summarize_session(conn, session_id)
                except Exception as mem_err:
                    logger.warning(f"Post-turn memory processing non-fatal error: {mem_err}")

            except OllamaConnectionError as conn_err:
                err_payload = {
                    "type": "error",
                    "session_id": session_id,
                    "error": str(conn_err),
                }
                await websocket.send_text(json.dumps(err_payload))
                await sync_hub.broadcast_session(session_id, err_payload, exclude=client)
            except OllamaError as ollama_err:
                err_payload = {
                    "type": "error",
                    "session_id": session_id,
                    "error": f"Ollama error: {ollama_err}",
                }
                await websocket.send_text(json.dumps(err_payload))
                await sync_hub.broadcast_session(session_id, err_payload, exclude=client)
            except Exception as exc:
                logger.exception("Unexpected error in chat streaming")
                err_payload = {
                    "type": "error",
                    "session_id": session_id,
                    "error": f"Streaming failure: {str(exc)}",
                }
                await websocket.send_text(json.dumps(err_payload))
                await sync_hub.broadcast_session(session_id, err_payload, exclude=client)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: device {device.get('id')}")
    finally:
        await sync_hub.unregister(client)
