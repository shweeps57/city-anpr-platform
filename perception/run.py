"""
run.py — Perception container entry point.

Startup sequence:
  1. Load camera configuration (config/cameras.json)
  2. Connect to Redis
  3. Load shared AI models (once, shared across all workers)
  4. Spawn one CameraWorker thread per camera
  5. Wait for SIGINT/SIGTERM → graceful shutdown
"""

import pyclipper  # CRITICAL: Must be imported before paddleocr to prevent zlib symbol collision!
import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path

import redis

from camera_worker import CameraWorker
from config import (
    CAMERA_CONFIG_PATH,
    REDIS_HOST,
    REDIS_PORT,
    VEHICLE_MODEL_PATH,
    PLATE_MODEL_PATH,
    PROCESSING_MODE,
)
from detector import VehicleDetector
from ocr import OCREngine
from plate_detector import PlateDetector
from sequential_orchestrator import SequentialOrchestrator

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("perception.run")


# ── Redis connection with retry ────────────────────────────────────────────────
def connect_redis(host: str, port: int, retries: int = 10) -> redis.Redis:
    for attempt in range(1, retries + 1):
        try:
            client = redis.Redis(host=host, port=port, decode_responses=True)
            client.ping()
            logger.info(f"✅ Redis connected at {host}:{port}")
            return client
        except Exception as exc:
            logger.warning(
                f"Redis connection attempt {attempt}/{retries} failed: {exc}"
            )
            time.sleep(3)
    logger.error("❌ Could not connect to Redis after multiple attempts. Exiting.")
    sys.exit(1)


# ── Camera config loader ───────────────────────────────────────────────────────
def load_camera_config(path: str) -> list[dict]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        logger.error(f"Camera config not found: {path}")
        sys.exit(1)
    with open(cfg_path) as f:
        cameras = json.load(f)
    logger.info(f"Loaded {len(cameras)} camera(s) from {path}")
    return cameras


# ── Model availability check ───────────────────────────────────────────────────
def check_models() -> None:
    missing = []
    for label, path in [
        ("Vehicle model", VEHICLE_MODEL_PATH),
        ("Plate model", PLATE_MODEL_PATH),
    ]:
        if not Path(path).exists():
            missing.append(f"  ❌ {label}: {path}")
        else:
            size_mb = Path(path).stat().st_size / 1_048_576
            logger.info(f"  ✅ {label}: {path} ({size_mb:.1f} MB)")

    if missing:
        logger.error(
            "Missing model files:\n"
            + "\n".join(missing)
            + "\n\nRun: python scripts/download_models.py"
        )
        sys.exit(1)


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    logger.info("=" * 60)
    logger.info("  ANPR Perception Container — Starting")
    logger.info("=" * 60)

    # 1. Verify models exist before trying to load them
    logger.info("Checking model files …")
    check_models()

    # 2. Connect to Redis
    redis_client = connect_redis(REDIS_HOST, REDIS_PORT)

    # 3. Load shared AI components (expensive — do once)
    logger.info("Loading AI models …")
    # CRITICAL: Initialize PaddleOCR BEFORE PyTorch (YOLO) to prevent OpenMP thread pool deadlocks!
    ocr_engine = OCREngine()
    vehicle_detector = VehicleDetector(VEHICLE_MODEL_PATH)
    plate_detector = PlateDetector(PLATE_MODEL_PATH)
    logger.info("✅ All AI models loaded.")

    # 4. Load camera configuration
    cameras = load_camera_config(CAMERA_CONFIG_PATH)

    # 5. Graceful shutdown event
    stop_event = threading.Event()

    def _shutdown(signum, frame):
        logger.info("Shutdown signal received — stopping workers …")
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # 6. Branch on processing mode
    logger.info(f"Processing mode: {PROCESSING_MODE}")

    if PROCESSING_MODE == "sequential":
        # ── Sequential mode: cameras process one-at-a-time in order ─────
        # Sort cameras by sequence_order (fallback to list position)
        cameras.sort(key=lambda c: c.get("sequence_order", float("inf")))

        logger.info(
            "Camera sequence: "
            + " → ".join(c['camera_id'] for c in cameras)
        )

        orchestrator = SequentialOrchestrator(
            cameras=cameras,
            vehicle_detector=vehicle_detector,
            plate_detector=plate_detector,
            ocr_engine=ocr_engine,
            redis_client=redis_client,
            stop_event=stop_event,
        )

        try:
            orchestrator.run()
        except KeyboardInterrupt:
            stop_event.set()

    else:
        # ── Parallel mode: all cameras in separate threads (default) ────
        threads = []
        for cam_cfg in cameras:
            worker = CameraWorker(
                camera_cfg=cam_cfg,
                vehicle_detector=vehicle_detector,
                plate_detector=plate_detector,
                ocr_engine=ocr_engine,
                redis_client=redis_client,
                stop_event=stop_event,
            )
            t = threading.Thread(
                target=worker.run,
                name=f"worker-{cam_cfg['camera_id']}",
                daemon=True,
            )
            threads.append(t)
            t.start()
            logger.info(f"Started worker thread for {cam_cfg['camera_id']}")

        # Wait for shutdown
        try:
            while not stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            stop_event.set()

        # Wait for threads to finish
        for t in threads:
            t.join(timeout=5)

    logger.info("Perception container stopped.")


if __name__ == "__main__":
    main()
