"""
City-Wide ANPR Intelligence Platform — FastAPI Backend

Central application server that exposes REST APIs for:
  - Vehicle trajectory reconstruction
  - Traffic analytics (density, heatmap, OD matrix, congestion)
  - Blacklist management
  - Real-time alert streaming via WebSocket

All endpoints consume canonical plate_event data from PostgreSQL/PostGIS.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg
import redis

from database.connection import get_db_connection, close_connections
from routes.trajectory import router as trajectory_router
from routes.analytics import router as analytics_router
from routes.blacklist import router as blacklist_router
from routes.alerts import router as alerts_router


# ─── Application lifecycle ───

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    yield
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


@app.post("/api/cameras", status_code=201, tags=["Cameras"])
def create_camera(camera: dict):
    """Register a new camera."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cameras (camera_id, name, latitude, longitude, road, direction)
                VALUES (%(camera_id)s, %(name)s, %(latitude)s, %(longitude)s,
                        %(road)s, %(direction)s)
                ON CONFLICT (camera_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    road = EXCLUDED.road,
                    direction = EXCLUDED.direction
                RETURNING *
            """, camera)
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
    """Query plate events with optional filters."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            query = "SELECT * FROM plate_events WHERE 1=1"
            params = []

            if plate_number:
                query += " AND plate_number = %s"
                params.append(plate_number.upper())
            if camera_id:
                query += " AND camera_id = %s"
                params.append(camera_id)

            query += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            rows = cur.fetchall()

    # Convert UUID and datetime for JSON serialization
    results = []
    for row in rows:
        r = dict(row)
        r["event_id"] = str(r["event_id"])
        r["timestamp"] = r["timestamp"].isoformat()
        # Remove PostGIS geometry object, keep lat/lon from camera
        r.pop("location", None)
        results.append(r)

    return results