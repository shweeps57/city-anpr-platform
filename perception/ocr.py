"""
ocr.py — PaddleOCR wrapper for reading text from plate crops.

PaddleOCR is expensive to initialise (downloads models on first run,
loads onto CPU). We initialise it exactly ONCE at module import time.
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Lazy singleton — initialised on first use ──────────────────────────────────
_ocr_engine = None


def _get_engine():
    global _ocr_engine
    if _ocr_engine is None:
        logger.info("Initialising PaddleOCR (first use — may take a moment) …")
        from paddleocr import PaddleOCR

        # use_angle_cls=True  → handles rotated/upside-down text
        # lang='en'           → English character set (covers Indian plates)
        # use_gpu=False       → CPU-only, no CUDA required
        # show_log=False      → suppress PaddleOCR's verbose output
        _ocr_engine = PaddleOCR(
            use_angle_cls=True,
            lang="en",
            use_gpu=False,
            show_log=False,
        )
        # PaddleOCR forces the root logger to WARNING when show_log=False.
        # We must restore it to INFO so our pipeline logs are visible.
        logging.getLogger().setLevel(logging.INFO)

        logger.info("✅ PaddleOCR engine ready.")
    return _ocr_engine


class OCREngine:
    """Thin wrapper around PaddleOCR providing a simple read() interface."""

    def __init__(self) -> None:
        # Force initialisation at object creation (rather than first call)
        _get_engine()

    def read(self, image: np.ndarray) -> Optional[str]:
        """
        Run OCR on a plate crop and return the recognised text.

        Args:
            image: BGR numpy array (preprocessed plate crop).

        Returns:
            Raw OCR string (may contain spaces/punctuation) or None if
            nothing was recognised.
        """
        if image is None or image.size == 0:
            return None

        engine = _get_engine()

        try:
            result = engine.ocr(image, cls=True)
        except Exception as exc:
            logger.warning(f"PaddleOCR error: {exc}")
            return None

        if not result or result[0] is None:
            return None

        # result is a list of pages; each page is a list of line results.
        # Each line result: [[bbox_points], (text, confidence)]
        texts = []
        for page in result:
            if page is None:
                continue
            for line in page:
                if line and len(line) >= 2:
                    text, confidence = line[1]
                    texts.append((text, confidence))

        if not texts:
            return None

        # Concatenate all detected text segments (plates are single-line)
        raw = "".join(t for t, _ in texts)
        return raw if raw.strip() else None
