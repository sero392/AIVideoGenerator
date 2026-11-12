"""In-process WebSocket connection manager for pushing live events to the panel."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    @property
    def count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, event: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(event)
            except Exception:  # noqa: BLE001
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


manager = ConnectionManager()
