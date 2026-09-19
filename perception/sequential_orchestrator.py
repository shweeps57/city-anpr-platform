"""
sequential_orchestrator.py — Sequential camera processing for trajectory tracking.

Processes cameras one-at-a-time in sequence_order. After each camera finishes,
confirmed plates are handed off to the next camera. The orchestrator builds
a trajectory log: {plate_number: [(camera_id, entry_frame, exit_frame, confidence), ...]}.

Key design decisions:
  - Each camera processes its ENTIRE video once (single-pass)
  - Adaptive frame skipping minimises frames processed
  - Departure grace period prevents false departures from brief occlusions
  - Cross-camera handoff passes confirmed plates to the next camera so it
    can specifically watch for those plates (but still detects new ones too)
"""

import json
import logging
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from camera_worker import CameraWorker
from config import MIN_PLATE_CONFIDENCE
from detector import VehicleDetector
from ocr import OCREngine
from plate_detector import PlateDetector

logger = logging.getLogger("perception.orchestrator")


class SequentialOrchestrator:
    """
    Orchestrates sequential camera processing for trajectory reconstruction.

    Usage:
        orchestrator = SequentialOrchestrator(
            cameras=sorted_camera_list,
            vehicle_detector=vehicle_detector,
            plate_detector=plate_detector,
            ocr_engine=ocr_engine,
            redis_client=redis_client,
            stop_event=stop_event,
        )
        orchestrator.run()
        # After run(), access orchestrator.trajectory_log for results
    """

    def __init__(
        self,
        cameras: list[dict],
        vehicle_detector: VehicleDetector,
        plate_detector: PlateDetector,
        ocr_engine: OCREngine,
        redis_client,
        stop_event: threading.Event,
    ) -> None:
        self._cameras = cameras
        self._vehicle_detector = vehicle_detector
        self._plate_detector = plate_detector
        self._ocr_engine = ocr_engine
        self._redis_client = redis_client
        self._stop_event = stop_event

        # ── Results ───────────────────────────────────────────────────────
        # {plate_number: [(camera_id, entry_frame, exit_frame, confidence, sequence_index), ...]}
        self.trajectory_log: dict[str, list[dict]] = defaultdict(list)

        # All confirmed plates across all cameras: {plate_number: best_confidence}
        self.all_confirmed_plates: dict[str, float] = {}

        # Per-camera processing stats
        self.camera_stats: list[dict] = []

    def run(self) -> None:
        """
        Main entry point — process all cameras in sequence.

        Blocks until all cameras are processed or stop_event is set.
        """
        logger.info("=" * 60)
        logger.info("  Sequential Orchestrator — Starting")
        logger.info(f"  Cameras to process: {len(self._cameras)}")
        logger.info("=" * 60)

        handoff_plates: set[str] = set()

        for idx, cam_cfg in enumerate(self._cameras):
            if self._stop_event.is_set():
                logger.info("Stop signal received — aborting sequence.")
                break

            camera_id = cam_cfg["camera_id"]
            camera_name = cam_cfg.get("name", camera_id)
            seq_index = cam_cfg.get("sequence_index", idx + 1)

            logger.info("")
            logger.info("─" * 60)
            logger.info(
                f"  Camera {idx + 1}/{len(self._cameras)}: "
                f"{camera_id} ({camera_name}) — seq={seq_index}"
            )
            if handoff_plates:
                logger.info(f"  Searching for {len(handoff_plates)} handed-off plate(s)")
            logger.info("─" * 60)

            start_time = time.time()

            # Process this camera
            worker_results = self._process_camera(
                cam_cfg=cam_cfg,
                sequence_index=seq_index,
                target_plates=handoff_plates if handoff_plates else None,
            )

            elapsed = time.time() - start_time

            # Collect results
            confirmed_in_camera = worker_results.get("confirmed_plates", {})
            trajectory_entries = worker_results.get("trajectory_entries", [])
            frames_processed = worker_results.get("frames_processed", 0)

            # Update global trajectory log
            for entry in trajectory_entries:
                plate = entry["plate_number"]
                self.trajectory_log[plate].append(entry)

            # Update global confirmed plates
            for plate, (track_id, conf) in confirmed_in_camera.items():
                if plate not in self.all_confirmed_plates or conf > self.all_confirmed_plates[plate]:
                    self.all_confirmed_plates[plate] = conf

            # Build handoff for next camera
            handoff_plates = self._build_handoff(confirmed_in_camera)

            # Log stats
            stats = {
                "camera_id": camera_id,
                "camera_name": camera_name,
                "sequence_index": seq_index,
                "plates_confirmed": len(confirmed_in_camera),
                "plates_list": list(confirmed_in_camera.keys()),
                "trajectory_entries": len(trajectory_entries),
                "elapsed_seconds": round(elapsed, 2),
                "handoff_to_next": len(handoff_plates),
            }
            self.camera_stats.append(stats)

            logger.info(
                f"  ✅ {camera_id} complete: "
                f"{len(confirmed_in_camera)} plate(s) confirmed, "
                f"{len(trajectory_entries)} trajectory entries, "
                f"{elapsed:.1f}s elapsed"
            )
            if confirmed_in_camera:
                for plate, (tid, conf) in confirmed_in_camera.items():
                    logger.info(f"     → {plate} (conf={conf:.2f})")

        # ── Final summary ─────────────────────────────────────────────────
        self._log_summary()

    def _process_camera(
        self,
        cam_cfg: dict,
        sequence_index: int,
        target_plates: Optional[set[str]] = None,
    ) -> dict:
        """
        Process a single camera's video (single-pass).

        Args:
            cam_cfg:         Camera configuration dict.
            sequence_index:  Position in the camera sequence.
            target_plates:   Plates to specifically look for (from previous camera).

        Returns:
            Dict with results: confirmed_plates, trajectory_entries.
        """
        # Track confirmations and departures via callbacks
        plate_confirmations: list[tuple[str, str, float]] = []
        vehicle_departures: list[tuple[str, Optional[str]]] = []

        def _on_plate_confirmed(track_id: str, plate: str, confidence: float):
            plate_confirmations.append((track_id, plate, confidence))
            logger.info(
                f"  📋 Plate confirmed: {plate} (track={track_id}, conf={confidence:.2f})"
            )

        def _on_vehicle_departed(track_id: str, plate: Optional[str]):
            vehicle_departures.append((track_id, plate))
            if plate:
                logger.info(
                    f"  🚗 Vehicle departed: {plate} (track={track_id}) "
                    f"— will search in next camera"
                )

        worker = CameraWorker(
            camera_cfg=cam_cfg,
            vehicle_detector=self._vehicle_detector,
            plate_detector=self._plate_detector,
            ocr_engine=self._ocr_engine,
            redis_client=self._redis_client,
            stop_event=self._stop_event,
            sequential=True,
            sequence_index=sequence_index,
            target_plates=target_plates,
            on_plate_confirmed=_on_plate_confirmed,
            on_vehicle_departed=_on_vehicle_departed,
        )

        # Run synchronously (blocking) — sequential mode
        worker.run()

        return {
            "confirmed_plates": worker.confirmed_plates,
            "trajectory_entries": worker.trajectory_entries,
        }

    def _build_handoff(
        self, confirmed_plates: dict[str, tuple[str, float]]
    ) -> set[str]:
        """
        Build the set of plates to hand off to the next camera.

        Only includes plates above MIN_PLATE_CONFIDENCE threshold.
        """
        handoff = set()
        for plate, (track_id, confidence) in confirmed_plates.items():
            if confidence >= MIN_PLATE_CONFIDENCE:
                handoff.add(plate)
            else:
                logger.debug(
                    f"  Skipping handoff for {plate} — "
                    f"confidence {confidence:.2f} < {MIN_PLATE_CONFIDENCE}"
                )
        return handoff

    def _log_summary(self) -> None:
        """Log the final trajectory summary."""
        logger.info("")
        logger.info("=" * 60)
        logger.info("  Sequential Processing — Complete")
        logger.info("=" * 60)

        # ── Per-camera stats ──────────────────────────────────────────────
        logger.info("")
        logger.info("Camera Processing Summary:")
        for stat in self.camera_stats:
            logger.info(
                f"  {stat['camera_id']} ({stat['camera_name']}): "
                f"{stat['plates_confirmed']} plates, "
                f"{stat['elapsed_seconds']}s"
            )

        # ── Trajectory summary ────────────────────────────────────────────
        logger.info("")
        logger.info(f"Total unique plates: {len(self.all_confirmed_plates)}")
        logger.info(f"Total trajectories: {len(self.trajectory_log)}")

        for plate, entries in self.trajectory_log.items():
            cameras_seen = [e["camera_id"] for e in entries]
            logger.info(
                f"  {plate}: seen in {len(entries)} camera(s) → "
                f"{' → '.join(cameras_seen)}"
            )

        # ── Publish trajectory summary to Redis ───────────────────────────
        self._publish_trajectory_summary()

    def _publish_trajectory_summary(self) -> None:
        """Publish the final trajectory log to Redis for the backend to consume."""
        try:
            summary = {
                "type": "trajectory_summary",
                "total_plates": len(self.all_confirmed_plates),
                "trajectories": {},
            }

            for plate, entries in self.trajectory_log.items():
                summary["trajectories"][plate] = {
                    "cameras": [
                        {
                            "camera_id": e["camera_id"],
                            "sequence_index": e.get("sequence_index", 0),
                            "entry_frame": e.get("entry_frame", 0),
                            "exit_frame": e.get("exit_frame", 0),
                        }
                        for e in entries
                    ],
                    "confidence": self.all_confirmed_plates.get(plate, 0.0),
                }

            self._redis_client.set(
                "trajectory:latest_summary",
                json.dumps(summary),
            )
            logger.info("✅ Trajectory summary published to Redis.")
        except Exception as exc:
            logger.error(f"Failed to publish trajectory summary: {exc}")
