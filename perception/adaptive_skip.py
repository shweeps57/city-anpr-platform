"""
adaptive_skip.py — Intelligent frame skipping for sequential processing.

Dynamically adjusts the frame skip rate based on what's happening in the scene:

  - No vehicles detected → scan mode (skip ADAPTIVE_SKIP_MAX frames)
  - Vehicle detected, plate not yet confirmed → track mode (skip ADAPTIVE_SKIP_MIN frames)
  - Plate confirmed, waiting for vehicle to leave → coast mode (skip midpoint frames)
  - All active tracks confirmed → back to scan mode

This minimises total frames processed while ensuring dense sampling
during the critical plate-reading window.
"""

import logging
from typing import Optional

from config import ADAPTIVE_SKIP_MIN, ADAPTIVE_SKIP_MAX

logger = logging.getLogger(__name__)


class AdaptiveFrameSkipper:
    """
    Per-camera adaptive frame skip controller.

    Call `update()` after each processed frame with the current scene state.
    Call `should_process(frame_idx)` to decide whether to process a frame.
    """

    # Internal states
    SCAN = "scan"         # No vehicles — skip aggressively
    TRACK = "track"       # Vehicle present, plate not confirmed — skip minimally
    COAST = "coast"       # All plates confirmed, waiting for departure — medium skip
    CONFIRM = "confirm"   # Just confirmed a plate — brief burst before coasting

    def __init__(
        self,
        skip_min: int = ADAPTIVE_SKIP_MIN,
        skip_max: int = ADAPTIVE_SKIP_MAX,
    ) -> None:
        self._skip_min = max(1, skip_min)
        self._skip_max = max(skip_min + 1, skip_max)
        self._skip_mid = max(1, (skip_min + skip_max) // 2)

        self._current_skip: int = self._skip_max
        self._state: str = self.SCAN
        self._last_processed_frame: int = 0

        # Track-level state: {track_id: "unconfirmed" | "confirmed"}
        self._track_states: dict[str, str] = {}

    @property
    def current_skip(self) -> int:
        """Current frame skip interval."""
        return self._current_skip

    @property
    def state(self) -> str:
        """Current adaptive state."""
        return self._state

    def should_process(self, frame_idx: int) -> bool:
        """Return True if this frame should be processed."""
        if frame_idx == 0:
            self._last_processed_frame = 0
            return True

        if frame_idx - self._last_processed_frame >= self._current_skip:
            self._last_processed_frame = frame_idx
            return True

        return False

    def update(
        self,
        active_track_ids: set[str],
        confirmed_track_ids: set[str],
    ) -> None:
        """
        Update the skip rate based on current scene state.

        Args:
            active_track_ids:    All track IDs currently visible in frame.
            confirmed_track_ids: Track IDs that have a confirmed plate number.
        """
        prev_state = self._state

        # Update internal track state map
        new_tracks = {}
        for tid in active_track_ids:
            if tid in confirmed_track_ids:
                new_tracks[tid] = "confirmed"
            else:
                new_tracks[tid] = "unconfirmed"
        self._track_states = new_tracks

        # Decide state
        if not active_track_ids:
            # No vehicles in frame — scan aggressively
            self._state = self.SCAN
            self._current_skip = self._skip_max

        elif any(s == "unconfirmed" for s in self._track_states.values()):
            # At least one vehicle without a confirmed plate — track densely
            self._state = self.TRACK
            self._current_skip = self._skip_min

        else:
            # All vehicles have confirmed plates — coast
            self._state = self.COAST
            self._current_skip = self._skip_mid

        if self._state != prev_state:
            logger.debug(
                f"[AdaptiveSkip] {prev_state} → {self._state} "
                f"(skip={self._current_skip}, tracks={len(active_track_ids)})"
            )

    def on_plate_confirmed(self, track_id: str) -> None:
        """Notify the skipper that a plate was just confirmed for this track."""
        if track_id in self._track_states:
            self._track_states[track_id] = "confirmed"

        # If all are now confirmed, switch to coast
        if self._track_states and all(
            s == "confirmed" for s in self._track_states.values()
        ):
            self._state = self.COAST
            self._current_skip = self._skip_mid
            logger.debug(
                f"[AdaptiveSkip] All tracks confirmed → COAST "
                f"(skip={self._current_skip})"
            )

    def on_track_departed(self, track_id: str) -> None:
        """Notify the skipper that a track has departed the FOV."""
        self._track_states.pop(track_id, None)

        if not self._track_states:
            self._state = self.SCAN
            self._current_skip = self._skip_max

    def reset(self) -> None:
        """Reset to initial scanning state (e.g. when switching cameras)."""
        self._current_skip = self._skip_max
        self._state = self.SCAN
        self._last_processed_frame = 0
        self._track_states.clear()
