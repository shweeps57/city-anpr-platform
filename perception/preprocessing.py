"""
preprocessing.py — Image preprocessing to improve OCR accuracy.

Pipeline:
    1. Convert to grayscale
    2. Apply CLAHE (Contrast Limited Adaptive Histogram Equalisation)
    3. Sharpen
    4. Resize to a minimum height for OCR readability

Start simple — add steps only if they demonstrably improve accuracy.
"""

import cv2
import numpy as np


def preprocess_plate(crop: np.ndarray) -> np.ndarray:
    """
    Preprocess a plate crop for OCR.

    Args:
        crop: BGR numpy array (the raw plate region).

    Returns:
        Preprocessed grayscale (or BGR) image ready for PaddleOCR.
    """
    if crop is None or crop.size == 0:
        return crop

    # ── Step 1: Ensure minimum height for readability ─────────────────────────
    min_height = 64
    h, w = crop.shape[:2]
    if h < min_height:
        scale = min_height / h
        crop = cv2.resize(crop, (int(w * scale), min_height), interpolation=cv2.INTER_CUBIC)

    # ── Step 2: Convert to grayscale ──────────────────────────────────────────
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    # ── Step 3: CLAHE — equalise contrast locally ─────────────────────────────
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    equalized = clahe.apply(gray)

    # ── Step 4: Sharpen ───────────────────────────────────────────────────────
    kernel = np.array([[0, -1, 0],
                       [-1, 5, -1],
                       [0, -1, 0]])
    sharpened = cv2.filter2D(equalized, -1, kernel)

    # ── Step 5: Back to BGR so PaddleOCR receives a 3-channel image ──────────
    result = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
    return result
