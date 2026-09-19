"""
City-Wide ANPR Intelligence Platform — FastAPI Backend

Central application server that exposes REST APIs for:
  - Vehicle trajectory reconstruction
  - Traffic analytics (density, heatmap, OD matrix, congestion)
  - Blacklist management
  - Real-time alert streaming via WebSocket

All endpoints consume canonical plate_event data from PostgreSQL/PostGIS.
"""

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import psycopg
import redis
from models.schemas import CameraBase, CameraResponse

from database.connection import get_db_connection, close_connections
from routes.trajectory import router as trajectory_router
from routes.analytics import router as analytics_router
from routes.blacklist import router as blacklist_router
from routes.alerts import router as alerts_router
from routes.dashboard import router as dashboard_router
from services.event_consumer import PlateEventConsumer


# ─── Application lifecycle ───

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    consumer = PlateEventConsumer()
    consumer_task = asyncio.create_task(consumer.run())
    try:
        yield
    finally:
        await consumer.stop()
        consumer_task.cancel()
        with suppress(asyncio.CancelledError):
            await consumer_task
        await close_connections()


app = FastAPI(
    title="City-Wide ANPR Intelligence Platform",
    description="Centralized AI-powered ANPR platform for distributed camera networks",
    version="0.1.0",
    lifespan=lifespan,
)

# ─── CORS (allow frontend on any port during dev) ───

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Register route modules ───

app.include_router(trajectory_router)
app.include_router(analytics_router)
app.include_router(blacklist_router)
app.include_router(alerts_router)
app.include_router(dashboard_router)


# ─── Root endpoints ───

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "anpr-backend"}


@app.get("/health", tags=["Health"])
def health():
    """Check connectivity to PostgreSQL and Redis."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                pg_ok = cur.fetchone()["?column?"] == 1
    except Exception:
        pg_ok = False

    try:
        r = redis.Redis(host="redis", port=6379)
        redis_ok = r.ping()
    except Exception:
        redis_ok = False

    return {"postgres": pg_ok, "redis": redis_ok}


# ─── Cameras CRUD (useful for setup and frontend) ───

@app.get("/api/cameras", tags=["Cameras"])
def list_cameras():
    """List all registered cameras with their metadata."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT camera_id, name, latitude, longitude, road, direction
                FROM cameras
                ORDER BY camera_id
            """)
            return cur.fetchall()


@app.post(
    "/api/cameras",
    response_model=CameraResponse,
    status_code=201,
    tags=["Cameras"],
)
def create_camera(camera: CameraBase):
    """Create or update a camera."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cameras (
                    camera_id, name, latitude, longitude, road, direction
                )
                VALUES (
                    %(camera_id)s, %(name)s, %(latitude)s, %(longitude)s,
                    %(road)s, %(direction)s
                )
                ON CONFLICT (camera_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    road = EXCLUDED.road,
                    direction = EXCLUDED.direction
                RETURNING camera_id, name, latitude, longitude, road, direction
                """,
                camera.model_dump()
            )
            row = cur.fetchone()
            conn.commit()

    return row


# ─── Plate events endpoint (for perception layer to push events) ───

@app.get("/api/events", tags=["Events"])
def list_events(
    plate_number: str | None = None,
    camera_id: str | None = None,
    limit: int = 100,
):
    """Query plate events with optional filters, joined with camera names."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT pe.event_id, pe.plate_number, pe.confidence,
                       pe.camera_id, pe.timestamp, pe.vehicle_type,
                       pe.direction, pe.track_id, pe.snapshot_path,
                       c.name AS camera_name, c.road
                FROM plate_events pe
                LEFT JOIN cameras c ON pe.camera_id = c.camera_id
                WHERE 1=1
            """
            params = []

            if plate_number:
                query += " AND pe.plate_number = %s"
                params.append(plate_number.upper())
            if camera_id:
                query += " AND pe.camera_id = %s"
                params.append(camera_id)

            query += " ORDER BY pe.timestamp DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        r = dict(row)
        r["event_id"] = str(r["event_id"])
        r["timestamp"] = r["timestamp"].isoformat()
        r.pop("location", None)
        results.append(r)

    return results


# ─── Serve frontend static files ───

frontend_path = Path("/app/frontend")
if frontend_path.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
