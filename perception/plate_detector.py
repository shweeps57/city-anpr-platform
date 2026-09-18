"""
plate_detector.py — License plate detection using a fine-tuned YOLO model.

Responsible for:
  - Loading plate_detector.pt once at startup
  - Running inference on a vehicle ROI crop
  - Returning the best plate bounding box (highest confidence)
  - Cropping and returning the plate image
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from config import PLATE_CONF_THRESHOLD, PLATE_MODEL_PATH

logger = logging.getLogger(__name__)


class PlateDetector:
    """Wraps the fine-tuned YOLO license plate detector."""

    def __init__(self, model_path: Optional[str] = None) -> None:
        path = model_path or PLATE_MODEL_PATH
        logger.info(f"Loading plate detector from: {path}")

        if not Path(path).exists():
            raise FileNotFoundError(
                f"Plate model not found at {path}\n"
                "Run: python scripts/download_models.py"
            )

        from ultralytics import YOLO

        self._model = YOLO(path)
        logger.info("✅ Plate detector loaded.")

    def detect(self, vehicle_crop: np.ndarray) -> list[dict]:
        """
        Detect license plates within a vehicle crop.

        Args:
            vehicle_crop: BGR image (numpy array) of the vehicle ROI.

        Returns:
            List of plate detection dicts:
            {
              "bbox": [x1, y1, x2, y2],   # coords relative to vehicle_crop
              "confidence": float,
            }
        """
        if vehicle_crop is None or vehicle_crop.size == 0:
            return []

        results = self._model(vehicle_crop, conf=PLATE_CONF_THRESHOLD, verbose=False)

        detections = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                detections.append(
                    {
                        "bbox": box.xyxy[0].tolist(),
                        "confidence": float(box.conf[0]),
                    }
                )

        # Sort by confidence descending; best plate first
        detections.sort(key=lambda d: d["confidence"], reverse=True)
        return detections

    def detect_and_crop(
        self, vehicle_crop: np.ndarray
    ) -> tuple[Optional[np.ndarray], float]:
        """
        Detect the best (highest-confidence) plate and return its crop.

        Returns:
            (plate_crop, confidence)  or  (None, 0.0) if no plate found.
        """
        detections = self.detect(vehicle_crop)
        if not detections:
            return None, 0.0

        best = detections[0]
        x1, y1, x2, y2 = [int(v) for v in best["bbox"]]

        # Guard against out-of-bounds
        h, w = vehicle_crop.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return None, 0.0

        plate_crop = vehicle_crop[y1:y2, x1:x2]
        return plate_crop, best["confidence"]
