"""
download_models.py
------------------
Run this ONCE on the host (not inside Docker) to download model weights.

Usage:
    python scripts/download_models.py

Downloads:
    models/yolov8n.pt          — Ultralytics YOLOv8 nano (COCO vehicle detector)
    models/plate_detector.pt   — License plate detector from HuggingFace
"""

import os
import sys
import urllib.request
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO_ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

YOLO_VEHICLE_PATH = MODELS_DIR / "yolov8n.pt"
PLATE_DETECTOR_PATH = MODELS_DIR / "plate_detector.pt"


# ── helpers ────────────────────────────────────────────────────────────────────
def download_file(url: str, dest: Path) -> None:
    """Download url → dest with a simple progress indicator."""
    print(f"  Downloading {dest.name} …")
    print(f"  Source: {url}")

    def _progress(block_num, block_size, total_size):
        if total_size > 0:
            pct = min(block_num * block_size / total_size * 100, 100)
            print(f"\r  Progress: {pct:5.1f}%", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, dest, reporthook=_progress)
        print(f"\r  [OK] Saved -> {dest}")
    except Exception as exc:
        print(f"\n  [ERROR] Failed: {exc}")
        sys.exit(1)


# ── vehicle detector (yolov8n.pt) ─────────────────────────────────────────────
def download_vehicle_model() -> None:
    if YOLO_VEHICLE_PATH.exists():
        size_mb = YOLO_VEHICLE_PATH.stat().st_size / 1_048_576
        print(f"[OK] yolov8n.pt already exists ({size_mb:.1f} MB) - skipping.")
        return

    print("\n[1/2] Downloading YOLOv8n vehicle detector …")
    # Ultralytics official GitHub release
    url = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt"
    download_file(url, YOLO_VEHICLE_PATH)


# ── plate detector (plate_detector.pt) ────────────────────────────────────────
def download_plate_model() -> None:
    if PLATE_DETECTOR_PATH.exists():
        size_mb = PLATE_DETECTOR_PATH.stat().st_size / 1_048_576
        print(f"[OK] plate_detector.pt already exists ({size_mb:.1f} MB) - skipping.")
        return

    print("\n[2/2] Downloading license plate detector …")
    # HuggingFace model: Koushim/yolov8-license-plate-detection
    url = (
        "https://huggingface.co/Koushim/yolov8-license-plate-detection"
        "/resolve/main/best.pt"
    )
    download_file(url, PLATE_DETECTOR_PATH)


# ── verify ─────────────────────────────────────────────────────────────────────
def verify() -> None:
    print("\n-- Verification -------------------------------------------------")
    all_ok = True
    for path in [YOLO_VEHICLE_PATH, PLATE_DETECTOR_PATH]:
        if path.exists():
            size_mb = path.stat().st_size / 1_048_576
            print(f"  [OK] {path.name:<25} {size_mb:7.1f} MB")
        else:
            print(f"  [MISSING] {path.name:<25} MISSING")
            all_ok = False

    if all_ok:
        print("\n[OK] All models ready. You can now run: docker compose up -d --build")
    else:
        print("\n[ERROR] Some models are missing. Check errors above.")
        sys.exit(1)


# ── main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  ANPR Platform — Model Download Script")
    print(f"  Target directory: {MODELS_DIR}")
    print("=" * 60)

    download_vehicle_model()
    download_plate_model()
    verify()
