"""Real-time multi-device WebSocket connection manager and synchronization bus."""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("aria.sync_hub")


class ClientConnection:
    """Represents an active authenticated WebSocket connection."""

    def __init__(self, websocket: WebSocket, device_id: str, device_name: str):
        self.websocket = websocket
        self.device_id = device_id
        self.device_name = device_name
        self.active_session_id: str | None = None

    async def send_json(self, data: dict[str, Any]) -> bool:
        """Send JSON message safely to this client. Returns False if send fails."""
        try:
            await self.websocket.send_text(json.dumps(data))
            return True
        except Exception as exc:
            logger.debug(f"Failed to send to device {self.device_id}: {exc}")
            return False


class SyncHub:
    """
    Central connection manager tracking active client connections
    and broadcasting real-time multi-device updates.
    """

    def __init__(self) -> None:
        self._connections: list[ClientConnection] = []
        self._lock = asyncio.Lock()

    async def register(
        self, websocket: WebSocket, device_id: str, device_name: str
    ) -> ClientConnection:
        """Register a newly authenticated client connection."""
        conn = ClientConnection(websocket, device_id, device_name)
        async with self._lock:
            self._connections.append(conn)
            logger.info(
                f"Client registered: {device_name} ({device_id}). "
                f"Total connections: {len(self._connections)}"
            )
        return conn

    async def unregister(self, client: ClientConnection) -> None:
        """Unregister a disconnected client connection."""
        async with self._lock:
            if client in self._connections:
                self._connections.remove(client)
                logger.info(
                    f"Client unregistered: {client.device_name} ({client.device_id}). "
                    f"Total connections: {len(self._connections)}"
                )

    def set_client_session(self, client: ClientConnection, session_id: str | None) -> None:
        """Update which chat session the client is currently viewing."""
        client.active_session_id = session_id

    async def broadcast_all(
        self, event: dict[str, Any], exclude: ClientConnection | None = None
    ) -> None:
        """Broadcast an event payload to all connected clients."""
        async with self._lock:
            targets = [c for c in self._connections if c is not exclude]

        if targets:
            await asyncio.gather(*(c.send_json(event) for c in targets), return_exceptions=True)

    async def broadcast_session(
        self,
        session_id: str,
        event: dict[str, Any],
        exclude: ClientConnection | None = None,
    ) -> None:
        """
        Broadcast an event to all clients currently viewing the specified session,
        or to all clients if they don't have an active session set.
        """
        async with self._lock:
            targets = [
                c
                for c in self._connections
                if c is not exclude
                and (c.active_session_id == session_id or c.active_session_id is None)
            ]

        if targets:
            await asyncio.gather(*(c.send_json(event) for c in targets), return_exceptions=True)

    async def disconnect_device(self, device_id: str, reason: str = "revoked") -> int:
        """
        Immediately disconnect all active connections belonging to a revoked device ID.
        """
        to_disconnect: list[ClientConnection] = []
        async with self._lock:
            for c in list(self._connections):
                if c.device_id == device_id:
                    to_disconnect.append(c)

        for client in to_disconnect:
            try:
                await client.send_json(
                    {"type": "auth_revoked", "reason": reason, "device_id": device_id}
                )
                await client.websocket.close(code=4003)
            except Exception:
                pass
            await self.unregister(client)

        return len(to_disconnect)

    @property
    def active_connections_count(self) -> int:
        return len(self._connections)


# Global singleton hub for application lifecycle
sync_hub = SyncHub()
