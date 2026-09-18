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
