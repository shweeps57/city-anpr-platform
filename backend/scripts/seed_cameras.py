"""Load camera configuration into PostgreSQL.

Run inside the backend container:
    python scripts/seed_cameras.py
"""

import json
import sys
from pathlib import Path


# Allow this file to be run directly from /app/scripts.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database.connection import get_db_connection
from models.schemas import CameraBase


CONFIG_PATH = Path("/config/cameras.json")


def load_cameras(config_path: Path = CONFIG_PATH) -> list[CameraBase]:
    """Read and validate camera records, ignoring perception-only fields."""
    try:
        raw_cameras = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Camera configuration was not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {config_path}: {exc}") from exc

    if not isinstance(raw_cameras, list):
        raise SystemExit("Camera configuration must be a JSON array.")

    try:
        return [
            CameraBase.model_validate(
                {
                    key: item.get(key)
                    for key in ("camera_id", "name", "latitude", "longitude", "road", "direction")
                }
            )
            for item in raw_cameras
        ]
    except Exception as exc:
        raise SystemExit(f"Camera validation failed: {exc}") from exc


def seed_cameras(cameras: list[CameraBase]) -> int:
    """Insert or update each camera in one database transaction."""
    query = """
        INSERT INTO cameras (camera_id, name, latitude, longitude, road, direction)
        VALUES (%(camera_id)s, %(name)s, %(latitude)s, %(longitude)s,
                %(road)s, %(direction)s)
        ON CONFLICT (camera_id) DO UPDATE SET
            name = EXCLUDED.name,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            road = EXCLUDED.road,
            direction = EXCLUDED.direction
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, [camera.model_dump() for camera in cameras])
        conn.commit()

    return len(cameras)


if __name__ == "__main__":
    cameras = load_cameras()
    count = seed_cameras(cameras)
    print(f"Seeded {count} camera(s).")
