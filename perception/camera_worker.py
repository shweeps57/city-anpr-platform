"""
camera_worker.py — Per-camera processing loop.

Each CameraWorker:
  1. Opens the video file with OpenCV
  2. Reads frames (respecting frame skip — fixed or adaptive)
  3. Runs vehicle detection + ByteTrack tracking
  4. For each tracked vehicle: runs plate detection → preprocessing → OCR
  5. Feeds valid OCR readings into TemporalVoter
  6. On confirmed plate: builds event, publishes to Redis
  7. In parallel mode: loops the video (simulates continuous feed)
     In sequential mode: single-pass with departure grace + callbacks

Supports two operating modes:
  - Parallel (default): Each camera runs independently in its own thread,
    looping the video indefinitely until stop_event is set.
  - Sequential: Camera processes its video once (single-pass), notifying
    the orchestrator via callbacks when plates are confirmed and vehicles
    depart the FOV.
"""

import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from adaptive_skip import AdaptiveFrameSkipper
from config import FRAME_SKIP, DEPARTURE_GRACE_FRAMES
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
        # ── Sequential mode options ───────────────────────────────────────
        sequential: bool = False,
        sequence_index: int = 0,
        target_plates: Optional[set[str]] = None,
        on_plate_confirmed: Optional[Callable[[str, str, float], None]] = None,
        on_vehicle_departed: Optional[Callable[[str, Optional[str]], None]] = None,
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

        # ── Sequential mode state ─────────────────────────────────────────
        self._sequential = sequential
        self._sequence_index = sequence_index
        self._target_plates = target_plates or set()
        self._on_plate_confirmed = on_plate_confirmed
        self._on_vehicle_departed = on_vehicle_departed

        # Departure grace: {track_id: consecutive_absent_frames}
        self._absent_counts: dict[str, int] = defaultdict(int)

        # Track first/last seen frame for each track_id
        self._track_first_frame: dict[str, int] = {}
        self._track_last_frame: dict[str, int] = {}

        # Adaptive frame skipper (only used in sequential mode)
        self._adaptive_skipper: Optional[AdaptiveFrameSkipper] = None
        if sequential:
            self._adaptive_skipper = AdaptiveFrameSkipper()

        # Results collected during sequential processing
        self.confirmed_plates: dict[str, tuple[str, float]] = {}
        # {plate_number: (track_id, confidence)}
        self.trajectory_entries: list[dict] = []
        # [{plate, camera_id, entry_frame, exit_frame, confidence}, ...]

    # ── public ─────────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Main loop — blocks until stop_event is set or video ends (sequential)."""
        log = logging.getLogger(f"worker.{self.camera_id}")

        if not Path(self.video_path).exists():
            log.error(f"Video not found: {self.video_path}  — worker exiting.")
            return

        log.info(f"Starting camera worker: {self.camera_id} → {self.video_path}")
        if self._sequential:
            log.info(
                f"  Mode: SEQUENTIAL (index={self._sequence_index}, "
                f"target_plates={len(self._target_plates)})"
            )

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
                    if self._sequential:
                        log.info(f"[{self.camera_id}] End of video — single pass complete.")
                        # Flush any remaining tracks as departed
                        self._flush_remaining_tracks(log)
                    else:
                        log.info(f"[{self.camera_id}] End of video — looping.")
                    break  # inner loop → reopen video (parallel) or exit (sequential)

                frame_idx += 1

                # ── Frame skip decision ────────────────────────────────────────
                if self._sequential and self._adaptive_skipper:
                    if not self._adaptive_skipper.should_process(frame_idx):
                        continue
                else:
                    if frame_idx % FRAME_SKIP != 0:
                        continue

                self._process_frame(frame, frame_idx, log)

                # Periodic progress log (every 30 processed frames)
                if self._sequential:
                    if (frame_idx % 50) == 0:
                        skip = self._adaptive_skipper.current_skip if self._adaptive_skipper else FRAME_SKIP
                        log.info(
                            f"[{self.camera_id}] frame={frame_idx} "
                            f"skip={skip} state={self._adaptive_skipper.state if self._adaptive_skipper else 'fixed'} "
                            f"active_tracks={len(self._active_tracks)}"
                        )
                else:
                    if (frame_idx // FRAME_SKIP) % 30 == 0:
                        log.info(
                            f"[{self.camera_id}] Processing frame {frame_idx} …"
                        )

            cap.release()

            # In sequential mode, don't loop — exit after single pass
            if self._sequential:
                break

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

            # Record first/last seen frames
            if track_id not in self._track_first_frame:
                self._track_first_frame[track_id] = frame_idx
            self._track_last_frame[track_id] = frame_idx

            # Reset absent counter since track is visible
            self._absent_counts.pop(track_id, None)

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
                    confirmed, plate_conf, vehicle_type, track_id, plate_crop,
                    frame_idx, log,
                )
                # Notify adaptive skipper
                if self._adaptive_skipper:
                    self._adaptive_skipper.on_plate_confirmed(track_id)

                # Notify orchestrator callback
                if self._on_plate_confirmed:
                    self._on_plate_confirmed(track_id, confirmed, plate_conf)

                # Store in results
                self.confirmed_plates[confirmed] = (track_id, plate_conf)

        # ── Handle tracks that disappeared this frame ───────────────────────────
        disappeared = self._active_tracks - current_track_ids

        if self._sequential:
            # Grace period: don't immediately declare departure
            for track_id in disappeared:
                self._absent_counts[track_id] += 1

                if self._absent_counts[track_id] >= DEPARTURE_GRACE_FRAMES:
                    # Confirmed departure
                    self._handle_departure(track_id, log)
        else:
            # Parallel mode: immediate departure (original behavior)
            for track_id in disappeared:
                result = self._voter.remove_track(track_id)
                if result:
                    log.info(
                        f"[{self.camera_id}] Late confirm for departed track={track_id}: '{result}'"
                    )

        # Also check: tracks that were absent but reappeared — reset their counter
        reappeared = current_track_ids & set(self._absent_counts.keys())
        for track_id in reappeared:
            if track_id in self._absent_counts:
                log.debug(
                    f"[{self.camera_id}] Track {track_id} reappeared after "
                    f"{self._absent_counts[track_id]} absent frames — resetting grace"
                )
                del self._absent_counts[track_id]

        self._active_tracks = current_track_ids

        # ── Update adaptive skipper ────────────────────────────────────────────
        if self._adaptive_skipper:
            confirmed_ids = {
                tid for tid in current_track_ids
                if self._voter.is_confirmed(tid)
            }
            self._adaptive_skipper.update(current_track_ids, confirmed_ids)

    def _handle_departure(self, track_id: str, log: logging.Logger) -> None:
        """Handle a confirmed vehicle departure (after grace period)."""
        # Get any late-confirmed plate
        result = self._voter.remove_track(track_id)

        plate_number = result
        if not plate_number:
            # Check if it was confirmed earlier
            for plate, (tid, _) in self.confirmed_plates.items():
                if tid == track_id:
                    plate_number = plate
                    break

        entry_frame = self._track_first_frame.get(track_id, 0)
        exit_frame = self._track_last_frame.get(track_id, 0)

        if plate_number:
            log.info(
                f"[{self.camera_id}] 🚗 Vehicle departed: track={track_id} "
                f"plate={plate_number} frames={entry_frame}→{exit_frame}"
            )
            # Build trajectory entry
            self.trajectory_entries.append({
                "plate_number": plate_number,
                "camera_id": self.camera_id,
                "entry_frame": entry_frame,
                "exit_frame": exit_frame,
                "sequence_index": self._sequence_index,
            })
        else:
            log.debug(
                f"[{self.camera_id}] Vehicle departed without confirmed plate: "
                f"track={track_id}"
            )

        # Notify orchestrator
        if self._on_vehicle_departed:
            self._on_vehicle_departed(track_id, plate_number)

        # Notify adaptive skipper
        if self._adaptive_skipper:
            self._adaptive_skipper.on_track_departed(track_id)

        # Cleanup
        self._absent_counts.pop(track_id, None)
        self._track_first_frame.pop(track_id, None)
        self._track_last_frame.pop(track_id, None)

    def _flush_remaining_tracks(self, log: logging.Logger) -> None:
        """At end of video, flush all active tracks as departed."""
        all_tracks = set(self._active_tracks) | set(self._absent_counts.keys())
        for track_id in all_tracks:
            self._handle_departure(track_id, log)
        self._active_tracks.clear()
        self._absent_counts.clear()

    def _emit_event(
        self,
        plate_number: str,
        confidence: float,
        vehicle_type: str,
        track_id: str,
        plate_crop: np.ndarray,
        frame_idx: int,
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
            sequence_index=self._sequence_index if self._sequential else None,
            entry_frame=self._track_first_frame.get(track_id) if self._sequential else None,
            exit_frame=frame_idx if self._sequential else None,
        )

        log.info(
            f"[{self.camera_id}] ✅ CONFIRMED plate={plate_number} "
            f"track={track_id} conf={confidence:.2f}"
        )

        publish_to_redis(event, self.redis_client)
