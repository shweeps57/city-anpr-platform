# Perception Directory

This directory contains the core Computer Vision and AI pipeline for the ANPR platform.

## Architecture
The perception pipeline runs as a standalone, multi-threaded Docker container (`anpr-perception`) that ingests video feeds and extracts license plate data. 

Key technologies used:
- **PyTorch & Ultralytics YOLOv8**: For high-speed vehicle and license plate detection.
- **PaddleOCR**: For highly accurate optical character recognition (OCR) of the localized license plate crops.
- **Temporal Majority Voting**: A custom buffering system that aggregates OCR reads over multiple frames for the same vehicle track to reduce misreads and noise.
- **Redis**: The pipeline serializes the final, validated plate reads and publishes them to the `plate-events` Redis stream.

## Entry Point
- `run.py` acts as the main entry point, loading the AI models (in a specific order to avoid OpenMP deadlocks) and spawning `CameraWorker` threads for each camera configured in `cameras.json`.
