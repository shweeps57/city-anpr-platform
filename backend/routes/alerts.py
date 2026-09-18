import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from services.alerts import get_recent_alerts, create_alert
from models.schemas import AlertCreate

router = APIRouter(tags=["Alerts"])

# Track active WebSocket connections for broadcasting
active_connections: list[WebSocket] = []


@router.get("/api/alerts")
def list_alerts(
    limit: int = Query(50, ge=1, le=500, description="Number of alerts to return"),
):
    """Get the most recent alerts."""
    return get_recent_alerts(limit=limit)


@router.post("/api/alerts", status_code=201)
async def post_alert(alert: AlertCreate):
    """
    Create a new alert and broadcast it to all connected WebSocket clients.
    """
    result = create_alert(
        plate_number=alert.plate_number,
        alert_type=alert.alert_type,
        message=alert.message,
        camera_id=alert.camera_id,
    )

    # Broadcast to all WebSocket clients
    disconnected = []
    for ws in active_connections:
        try:
            await ws.send_text(json.dumps(result))
        except Exception:
            disconnected.append(ws)

    for ws in disconnected:
        active_connections.remove(ws)

    return result


@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket endpoint for real-time alert streaming.

    Clients connect here to receive live alerts as they are created.
    """
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Keep connection alive; client can send pings
            data = await websocket.receive_text()
            # Echo back as a simple keepalive acknowledgment
            await websocket.send_text(json.dumps({"type": "pong", "data": data}))
    except WebSocketDisconnect:
        active_connections.remove(websocket)
