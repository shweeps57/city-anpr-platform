"""
event.py — Build and publish canonical plate events.

A plate event is the single unit of data that feeds:
  - Trajectory (same plate, multiple cameras, ordered by time)
  - Analytics  (counts, heatmaps, OD)
  - Alerts     (blacklist lookup)

Schema matches plate_events in PostgreSQL:
    event_id, plate_number, confidence, camera_id,
    timestamp, vehicle_type, direction, track_id,
    location, snapshot_path
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from config import REDIS_STREAM, SNAPSHOT_DIR

logger = logging.getLogger(__name__)


def build_event(
    plate_number: str,
    confidence: float,
    camera_id: str,
    vehicle_type: str = "car",
    direction: Optional[str] = None,
    track_id: Optional[str] = None,
    snapshot: Optional[np.ndarray] = None,
    sequence_index: Optional[int] = None,
    entry_frame: Optional[int] = None,
    exit_frame: Optional[int] = None,
) -> dict:
    """
    Construct a canonical plate event dict.

    Args:
        plate_number:    Confirmed plate string e.g. "PB65AB1234"
        confidence:      Float 0–1 from OCR / plate detector
        camera_id:       String e.g. "CAM_01"
        vehicle_type:    "car" | "motorcycle" | "bus" | "truck"
        direction:       Camera direction string (from cameras.json)
        track_id:        ByteTrack track ID as string
        snapshot:        BGR numpy array of the plate crop (saved as JPEG)
        sequence_index:  Camera position in sequential processing order
        entry_frame:     Frame number when vehicle first appeared in this camera
        exit_frame:      Frame number when vehicle was last seen in this camera

    Returns:
        Dict matching the plate_events schema.
    """
    event_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    snapshot_path = None
    if snapshot is not None:
        snapshot_path = _save_snapshot(snapshot, event_id)

    event = {
        "event_id": event_id,
        "plate_number": plate_number,
        "confidence": round(confidence, 4),
        "camera_id": camera_id,
        "timestamp": timestamp,
        "vehicle_type": vehicle_type,
        "direction": direction,
        "track_id": track_id,
        "location": None,          # Resolved later by backend from camera GIS data
        "snapshot_path": snapshot_path,
        "sequence_index": sequence_index,
        "entry_frame": entry_frame,
        "exit_frame": exit_frame,
    }

    return event


def _save_snapshot(image: np.ndarray, event_id: str) -> Optional[str]:
    """Save plate crop as JPEG to SNAPSHOT_DIR. Returns the file path."""
    try:
        Path(SNAPSHOT_DIR).mkdir(parents=True, exist_ok=True)
        filename = f"evt_{event_id}.jpg"
        path = os.path.join(SNAPSHOT_DIR, filename)
        cv2.imwrite(path, image)
        return path
    except Exception as exc:
        logger.warning(f"Could not save snapshot: {exc}")
        return None


def publish_to_redis(event: dict, redis_client) -> bool:
    """
    Publish a plate event to the Redis Stream 'plate-events'.

    Uses XADD with all dict values serialised as strings (Redis streams
    store field–value pairs, not JSON blobs).

    Returns True on success, False on failure.
    """
    try:
        # Flatten event dict to str→str mapping for Redis streams
        fields = {k: (json.dumps(v) if v is not None else "") for k, v in event.items()}
        redis_client.xadd(REDIS_STREAM, fields)
        logger.info(
            f"[Redis] Published event: plate={event['plate_number']} "
            f"camera={event['camera_id']} track={event['track_id']}"
        )
        return True
    except Exception as exc:
        logger.error(f"[Redis] Failed to publish event: {exc}")
        return False
