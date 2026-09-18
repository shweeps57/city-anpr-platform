"""In-process WebSocket broadcasting for alert notifications."""

import json

from fastapi import WebSocket


class AlertHub:
    """Maintain WebSocket clients connected to the alert feed."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, alert: dict) -> None:
        """Send an alert to every live client and discard failed connections."""
        disconnected: list[WebSocket] = []
        message = json.dumps(alert)
        for websocket in self._connections:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(websocket)


alert_hub = AlertHub()
