"""
detector.py — Vehicle detection using YOLOv8n (COCO pretrained).

Responsible for:
  - Loading yolov8n.pt once at startup
  - Running inference on a frame
  - Filtering detections to vehicle classes only
  - Returning detections as a list of dicts
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from config import VEHICLE_CLASSES, VEHICLE_CONF_THRESHOLD, VEHICLE_MODEL_PATH

logger = logging.getLogger(__name__)


class VehicleDetector:
    """Wraps YOLOv8n for vehicle detection with ByteTrack tracking."""

    # COCO class names relevant to vehicles
    VEHICLE_CLASS_NAMES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

    def __init__(self, model_path: Optional[str] = None) -> None:
        path = model_path or VEHICLE_MODEL_PATH
        logger.info(f"Loading vehicle detector from: {path}")

        if not Path(path).exists():
            raise FileNotFoundError(
                f"Vehicle model not found at {path}\n"
                "Run: python scripts/download_models.py"
            )

        # Import here so startup errors are clear
        from ultralytics import YOLO

        self._model = YOLO(path)
        logger.info("✅ Vehicle detector loaded.")

    def detect(self, frame: np.ndarray) -> list[dict]:
        """
        Run detection (no tracking) on a single frame.

        Returns list of dicts:
            {
              "bbox": [x1, y1, x2, y2],   # absolute pixel coords
              "confidence": float,
              "class_id": int,
              "class_name": str,
            }
        """
        results = self._model(
            frame,
            classes=VEHICLE_CLASSES,
            conf=VEHICLE_CONF_THRESHOLD,
            verbose=False,
        )

        detections = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                detections.append(
                    {
                        "bbox": box.xyxy[0].tolist(),
                        "confidence": float(box.conf[0]),
                        "class_id": cls_id,
                        "class_name": self.VEHICLE_CLASS_NAMES.get(cls_id, "vehicle"),
                    }
                )
        return detections

    def track(self, frame: np.ndarray, persist: bool = True) -> list[dict]:
        """
        Run detection + ByteTrack tracking on a single frame.

        Returns list of dicts:
            {
              "bbox": [x1, y1, x2, y2],
              "confidence": float,
              "class_id": int,
              "class_name": str,
              "track_id": str,             # unique track identity within camera
            }
        """
        results = self._model.track(
            frame,
            classes=VEHICLE_CLASSES,
            conf=VEHICLE_CONF_THRESHOLD,
            tracker="bytetrack.yaml",
            persist=persist,
            verbose=False,
        )

        detections = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                track_id = (
                    str(int(box.id[0])) if box.id is not None else None
                )
                cls_id = int(box.cls[0])
                detections.append(
                    {
                        "bbox": box.xyxy[0].tolist(),
                        "confidence": float(box.conf[0]),
                        "class_id": cls_id,
                        "class_name": self.VEHICLE_CLASS_NAMES.get(cls_id, "vehicle"),
                        "track_id": track_id,
                    }
                )
        return detections
