from typing import List
import pandas as pd
from base import DataProvider

class CSVProvider(DataProvider):
    def __init__(self, folder: str | None = None):
        """Optionally set a folder to look for per-symbol CSVs (raw bars only)."""
        pass

    def get_bars(self, symbols: List[str], start: str, end: str, resolution: str) -> pd.DataFrame:
        """Load per-symbol CSVs, normalize to raw canonical shape, clip to timeframe, return (no indicators)."""
        pass
