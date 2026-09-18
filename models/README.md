# Models Directory

This directory stores the pre-trained neural network weights used by the perception pipeline.

## Required Models
To run the AI perception container, the following model weights must be present here:
- **`yolov8n.pt`**: Ultralytics YOLOv8 nano model for general vehicle detection.
- **`plate_detector.pt`**: Custom or fine-tuned YOLO model for license plate localization.

These models are mounted as read-only volumes into the `anpr-perception` container at runtime. If this folder is empty, you must run the `download_models.py` script located in the `scripts/` directory before starting Docker.
