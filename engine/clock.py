
class BarClock:
    def __init__(self, timestamps, skip_weekends: bool = True):
        """Hold the timeline and the policy for skipping weekend dates (for daily data)."""
        pass

    def __iter__(self):
        """Yield timestamps in order, applying any simple filters (e.g., weekend skip)."""
        pass

# Suggested helpers:
# - def _is_weekend(ts) -> bool
# - def _is_holiday(ts) -> bool