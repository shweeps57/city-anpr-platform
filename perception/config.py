"""
config.py — Runtime configuration for the perception container.
All values are read from environment variables with sensible defaults.
"""

import os

# ── Model paths (inside container via volume mount) ────────────────────────────
VEHICLE_MODEL_PATH: str = os.getenv("VEHICLE_MODEL", "/app/models/yolov8n.pt")
PLATE_MODEL_PATH: str = os.getenv("PLATE_MODEL", "/app/models/plate_detector.pt")

# ── Camera configuration ───────────────────────────────────────────────────────
CAMERA_CONFIG_PATH: str = os.getenv("CAMERA_CONFIG", "/app/config/cameras.json")

# ── Redis ──────────────────────────────────────────────────────────────────────
REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_STREAM: str = os.getenv("REDIS_STREAM", "plate-events")

# ── Detection thresholds ───────────────────────────────────────────────────────
# Minimum confidence for vehicle detection
VEHICLE_CONF_THRESHOLD: float = float(os.getenv("VEHICLE_CONF", "0.4"))
# Minimum confidence for plate detection
PLATE_CONF_THRESHOLD: float = float(os.getenv("PLATE_CONF", "0.4"))

# COCO class IDs for vehicles (car=2, motorcycle=3, bus=5, truck=7)
VEHICLE_CLASSES: list[int] = [2, 3, 5, 7]

# ── Temporal voting ────────────────────────────────────────────────────────────
# Minimum number of OCR readings before a plate is confirmed
MIN_VOTES: int = int(os.getenv("MIN_VOTES", "3"))
# Maximum frames to accumulate votes before forcing a decision
MAX_VOTE_FRAMES: int = int(os.getenv("MAX_VOTE_FRAMES", "60"))

# ── Snapshot output ────────────────────────────────────────────────────────────
SNAPSHOT_DIR: str = os.getenv("SNAPSHOT_DIR", "/app/data/snapshots")

# ── Frame processing ───────────────────────────────────────────────────────────
# Process every Nth frame (1 = every frame, 3 = every 3rd frame, etc.)
FRAME_SKIP: int = int(os.getenv("FRAME_SKIP", "3"))

# ── Processing mode ────────────────────────────────────────────────────────────
# "parallel" = current behavior (all cameras in separate threads)
# "sequential" = cameras process one-at-a-time in sequence_order for trajectory tracking
PROCESSING_MODE: str = os.getenv("PROCESSING_MODE", "parallel")

# ── Adaptive frame skipping (sequential mode) ─────────────────────────────────
# Min skip = dense processing when actively tracking a vehicle
ADAPTIVE_SKIP_MIN: int = int(os.getenv("ADAPTIVE_SKIP_MIN", "2"))
# Max skip = sparse scanning when no vehicles are present
ADAPTIVE_SKIP_MAX: int = int(os.getenv("ADAPTIVE_SKIP_MAX", "8"))

# ── Departure detection ───────────────────────────────────────────────────────
# Number of consecutive frames with no detection before declaring vehicle departed
DEPARTURE_GRACE_FRAMES: int = int(os.getenv("DEPARTURE_GRACE_FRAMES", "5"))

# ── Cross-camera handoff ──────────────────────────────────────────────────────
# Minimum confidence threshold for a plate to be handed off to the next camera
MIN_PLATE_CONFIDENCE: float = float(os.getenv("MIN_PLATE_CONFIDENCE", "0.6"))
