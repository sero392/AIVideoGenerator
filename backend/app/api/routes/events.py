from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket.manager import manager

router = APIRouter(tags=["events"])


@router.websocket("/ws/events")
async def events(websocket: WebSocket) -> None:
    """Server → client event stream (heartbeats now; recording/clip events later)."""
    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "connected"})
        while True:
            # Keep the socket open; clients may send "ping".
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
