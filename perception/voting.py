"""
voting.py — Temporal voting for stable plate recognition.

For each tracked vehicle (identified by track_id), we accumulate OCR
readings over multiple frames. Once we have MIN_VOTES readings, we take
the majority vote as the confirmed plate number.

Key insight: a single OCR frame may be wrong; the consensus across 3–5
frames is much more reliable.
"""

import logging
from collections import defaultdict, Counter
from typing import Optional

from config import MIN_VOTES, MAX_VOTE_FRAMES

logger = logging.getLogger(__name__)


class TemporalVoter:
    """
    Per-camera temporal voter.

    Maintains per-track vote buffers. When a track accumulates enough
    votes OR reaches max_frames, the best reading is returned and the
    buffer is flushed.
    """

    def __init__(
        self,
        min_votes: int = MIN_VOTES,
        max_frames: int = MAX_VOTE_FRAMES,
    ) -> None:
        self.min_votes = min_votes
        self.max_frames = max_frames

        # track_id → list of (plate_str, confidence) readings
        self._votes: dict[str, list[tuple[str, float]]] = defaultdict(list)
        # track_id → number of frames seen (including frames with no valid OCR)
        self._frame_counts: dict[str, int] = defaultdict(int)
        # track_id → already emitted a confirmed event (prevent duplicates)
        self._emitted: set[str] = set()

    def add_reading(
        self, track_id: str, plate: str, confidence: float
    ) -> Optional[str]:
        """
        Record an OCR reading for a track.

        Args:
            track_id:   Tracker-assigned ID for this vehicle.
            plate:      Validated plate string (e.g. "PB65AB1234").
            confidence: OCR or plate-detector confidence.

        Returns:
            Confirmed plate string if threshold is reached, else None.
        """
        if track_id in self._emitted:
            return None

        self._votes[track_id].append((plate, confidence))
        return self._check(track_id)

    def tick(self, track_id: str) -> Optional[str]:
        """
        Call once per frame for every active track, even if no valid OCR
        reading was produced. Forces a decision if max_frames is reached.
        """
        if track_id in self._emitted:
            return None

        self._frame_counts[track_id] += 1

        if self._frame_counts[track_id] >= self.max_frames:
            return self._force_decide(track_id)

        return None

    def remove_track(self, track_id: str) -> Optional[str]:
        """
        Called when a track disappears from the frame (vehicle left FOV).
        Forces a decision if we have any votes at all.
        """
        if track_id in self._emitted:
            self._cleanup(track_id)
            return None

        result = self._force_decide(track_id)
        self._cleanup(track_id)
        return result

    # ── internal ───────────────────────────────────────────────────────────────

    def _check(self, track_id: str) -> Optional[str]:
        """Return confirmed plate if min_votes reached."""
        votes = self._votes[track_id]
        if len(votes) >= self.min_votes:
            return self._decide(track_id)
        return None

    def _force_decide(self, track_id: str) -> Optional[str]:
        """Return the best plate we have, even if below min_votes."""
        if not self._votes.get(track_id):
            return None
        return self._decide(track_id)

    def _decide(self, track_id: str) -> Optional[str]:
        """Majority vote over accumulated readings."""
        votes = self._votes[track_id]
        if not votes:
            return None

        plate_counts: Counter = Counter(plate for plate, _ in votes)
        best_plate, best_count = plate_counts.most_common(1)[0]

        logger.info(
            f"[voter] track={track_id} confirmed='{best_plate}' "
            f"votes={best_count}/{len(votes)}"
        )

        self._emitted.add(track_id)
        return best_plate

    def _cleanup(self, track_id: str) -> None:
        self._votes.pop(track_id, None)
        self._frame_counts.pop(track_id, None)
        self._emitted.discard(track_id)

    def reset_track(self, track_id: str) -> None:
        """Fully reset a track (e.g. to allow re-detection)."""
        self._cleanup(track_id)
