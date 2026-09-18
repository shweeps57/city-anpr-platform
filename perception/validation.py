"""
validation.py — Indian license plate normalisation, confusion correction,
and format validation.

Indian plate format (standard):
    ^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$

Examples:
    PB65AB1234   ← Punjab, 65, series AB, number 1234
    DL5SAB1234   ← Delhi, 5S, series AB, number 1234
    MH12AB1234   ← Maharashtra

OCR confusion corrections are POSITION-AWARE:
  - Positions that must be letters: digits corrected to look-alike letters
  - Positions that must be digits: letters corrected to look-alike digits
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Plate regex ────────────────────────────────────────────────────────────────
# Allows 1 or 2 letter series (PB65A1234 or PB65AB1234)
PLATE_PATTERN = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$")

# ── Confusion maps ─────────────────────────────────────────────────────────────
# When the position MUST be a digit, replace these letter look-alikes
LETTER_TO_DIGIT = {
    "O": "0",
    "I": "1",
    "Z": "2",
    "S": "5",
    "B": "8",
    "G": "6",
    "T": "7",
}

# When the position MUST be a letter, replace these digit look-alikes
DIGIT_TO_LETTER = {
    "0": "O",
    "1": "I",
    "2": "Z",
    "5": "S",
    "8": "B",
    "6": "G",
    "7": "T",
}


def normalize_plate(raw: str) -> str:
    """
    Strip spaces, hyphens, punctuation and convert to uppercase.
    e.g. "pb 65 ab 1234" → "PB65AB1234"
    """
    if not raw:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw)
    return cleaned.upper()


def apply_confusion_correction(text: str) -> str:
    """
    Apply position-aware OCR confusion correction.

    Indian plate structure:
        [0:2]  = 2 letters (state code)    → must be letters
        [2:4]  = 2 digits (district code)  → must be digits
        [4:-4] = 1–2 letters (series)      → must be letters
        [-4:]  = 4 digits (number)         → must be digits

    Only applies corrections where the type (letter/digit) is unambiguous.
    """
    if len(text) < 8:
        # Too short to safely apply positional correction
        return text

    chars = list(text)
    n = len(chars)

    # Positions that MUST be digits: [2], [3], last 4 characters
    digit_positions = {2, 3} | set(range(n - 4, n))

    # Positions that MUST be letters: [0], [1], middle portion
    letter_positions = {0, 1} | set(range(4, n - 4))

    for i, ch in enumerate(chars):
        if i in digit_positions and ch.isalpha():
            chars[i] = LETTER_TO_DIGIT.get(ch, ch)
        elif i in letter_positions and ch.isdigit():
            chars[i] = DIGIT_TO_LETTER.get(ch, ch)

    return "".join(chars)


def validate_plate(text: str) -> bool:
    """
    Return True if text matches the standard Indian plate regex.
    """
    return bool(PLATE_PATTERN.match(text))


def process_ocr_output(raw: str) -> Optional[str]:
    """
    Full processing pipeline for a raw OCR string:
      1. Normalise
      2. Apply confusion correction
      3. Validate

    Returns the cleaned plate string if valid, else None.
    """
    if not raw:
        return None

    normalised = normalize_plate(raw)
    corrected = apply_confusion_correction(normalised)

    if validate_plate(corrected):
        return corrected

    # Log near-misses for debugging
    if len(corrected) >= 8:
        logger.debug(f"Plate rejected: '{corrected}' (from raw: '{raw}')")

    return None
