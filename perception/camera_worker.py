"""
camera_worker.py — Per-camera processing loop.

Each CameraWorker:
  1. Opens the video file with OpenCV
  2. Reads frames (respecting FRAME_SKIP)
  3. Runs vehicle detection + ByteTrack tracking
  4. For each tracked vehicle: runs plate detection → preprocessing → OCR
  5. Feeds valid OCR readings into TemporalVoter
  6. On confirmed plate: builds event, publishes to Redis
  7. Loops the video when it ends (simulates a continuous camera feed)
"""

import logging
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from config import FRAME_SKIP
from detector import VehicleDetector
from event import build_event, publish_to_redis
from ocr import OCREngine
from plate_detector import PlateDetector
from preprocessing import preprocess_plate
from validation import process_ocr_output
from voting import TemporalVoter

logger = logging.getLogger(__name__)


class CameraWorker:
    """Runs the full ANPR pipeline for one virtual camera."""

    def __init__(
        self,
        camera_cfg: dict,
        vehicle_detector: VehicleDetector,
        plate_detector: PlateDetector,
        ocr_engine: OCREngine,
        redis_client,
        stop_event,
    ) -> None:
        self.camera_id: str = camera_cfg["camera_id"]
        self.video_path: str = camera_cfg["video_path"]
        self.direction: Optional[str] = camera_cfg.get("direction")
        self.redis_client = redis_client
        self.stop_event = stop_event

        # Shared AI components (initialised once in run.py, passed in)
        self._vehicle_detector = vehicle_detector
        self._plate_detector = plate_detector
        self._ocr = ocr_engine

        # Per-camera state
        self._voter = TemporalVoter()
        self._active_tracks: set[str] = set()

    # ── public ─────────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Main loop — blocks until stop_event is set."""
        log = logging.getLogger(f"worker.{self.camera_id}")

        if not Path(self.video_path).exists():
            log.error(f"Video not found: {self.video_path}  — worker exiting.")
            return

        log.info(f"Starting camera worker: {self.camera_id} → {self.video_path}")

        while not self.stop_event.is_set():
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                log.error(f"Cannot open video: {self.video_path}")
                time.sleep(5)
                continue

            frame_idx = 0
            while not self.stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    log.info(f"[{self.camera_id}] End of video — looping.")
                    break  # inner loop → reopen video

                frame_idx += 1
                if frame_idx % FRAME_SKIP != 0:
                    continue

                self._process_frame(frame, frame_idx, log)

                # Periodic progress log (every 30 processed frames)
                if (frame_idx // FRAME_SKIP) % 30 == 0:
                    log.info(
                        f"[{self.camera_id}] Processing frame {frame_idx} …"
                    )

            cap.release()

        log.info(f"[{self.camera_id}] Worker stopped.")

    # ── internal ───────────────────────────────────────────────────────────────

    def _process_frame(
        self, frame: np.ndarray, frame_idx: int, log: logging.Logger
    ) -> None:
        """Run the full pipeline on one frame."""

        # ── 1. Vehicle detection + tracking ────────────────────────────────────
        try:
            vehicles = self._vehicle_detector.track(frame)
        except Exception as exc:
            log.warning(f"[{self.camera_id}] Vehicle detection error: {exc}")
            return

        current_track_ids = set()

        for v in vehicles:
            track_id = v.get("track_id")
            if track_id is None:
                continue

            current_track_ids.add(track_id)
            vehicle_type = v.get("class_name", "car")

            # ── 2. Crop vehicle ROI ────────────────────────────────────────────
            x1, y1, x2, y2 = [int(c) for c in v["bbox"]]
            vehicle_crop = frame[
                max(0, y1):min(frame.shape[0], y2),
                max(0, x1):min(frame.shape[1], x2),
            ]
            if vehicle_crop.size == 0:
                continue

            # ── 3. Plate detection ─────────────────────────────────────────────
            try:
                plate_crop, plate_conf = self._plate_detector.detect_and_crop(
                    vehicle_crop
                )
            except Exception as exc:
                log.debug(f"Plate detection error: {exc}")
                self._voter.tick(track_id)
                continue

            if plate_crop is None:
                self._voter.tick(track_id)
                continue

            log.debug(
                f"[{self.camera_id}] f{frame_idx} track={track_id} "
                f"plate_conf={plate_conf:.2f}"
            )

            # ── 4. Preprocessing ───────────────────────────────────────────────
            try:
                processed = preprocess_plate(plate_crop)
            except Exception:
                processed = plate_crop

            # ── 5. OCR ─────────────────────────────────────────────────────────
            try:
                raw_text = self._ocr.read(processed)
            except Exception as exc:
                log.debug(f"OCR error: {exc}")
                self._voter.tick(track_id)
                continue

            if not raw_text:
                self._voter.tick(track_id)
                continue

            # ── 6. Validation ──────────────────────────────────────────────────
            validated = process_ocr_output(raw_text)
            if not validated:
                log.debug(
                    f"[{self.camera_id}] track={track_id} OCR rejected: '{raw_text}'"
                )
                self._voter.tick(track_id)
                continue

            log.debug(
                f"[{self.camera_id}] track={track_id} valid OCR: '{validated}'"
            )

            # ── 7. Temporal voting ─────────────────────────────────────────────
            confirmed = self._voter.add_reading(track_id, validated, plate_conf)

            if confirmed:
                self._emit_event(
                    confirmed, plate_conf, vehicle_type, track_id, plate_crop, log
                )

        # ── Handle tracks that disappeared this frame ───────────────────────────
        disappeared = self._active_tracks - current_track_ids
        for track_id in disappeared:
            result = self._voter.remove_track(track_id)
            if result:
                # We get a last-chance confirmation from the voter
                log.info(
                    f"[{self.camera_id}] Late confirm for departed track={track_id}: '{result}'"
                )

        self._active_tracks = current_track_ids

    def _emit_event(
        self,
        plate_number: str,
        confidence: float,
        vehicle_type: str,
        track_id: str,
        plate_crop: np.ndarray,
        log: logging.Logger,
    ) -> None:
        """Build the canonical event and publish it to Redis."""
        event = build_event(
            plate_number=plate_number,
            confidence=confidence,
            camera_id=self.camera_id,
            vehicle_type=vehicle_type,
            direction=self.direction,
            track_id=track_id,
            snapshot=plate_crop,
        )

        log.info(
            f"[{self.camera_id}] ✅ CONFIRMED plate={plate_number} "
            f"track={track_id} conf={confidence:.2f}"
        )

        publish_to_redis(event, self.redis_client)
