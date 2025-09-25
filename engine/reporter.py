from typing import List, Dict, Any
import pandas as pd

class Reporter:
    def __init__(self, out_dir: str):
        """Remember output path; prep buffers (e.g., equity points)."""
        pass

    def record_equity(self, ts, equity: float) -> None:
        """Append one timepoint to the equity curve."""
        pass

    def write_csvs(self, trades: List[Dict[str, Any]], positions_hist: List[Dict[str, Any]]) -> None:
        """Persist equity/trades/positions to CSV files."""
        pass

    def write_plots(self) -> None:
        """Generate basic plots (equity curve, drawdown most important imo) and save to images."""
        pass

    def write_manifest(self, payload: Dict[str, Any]) -> None:
        """Save a small JSON file with run metadata and computed KPIs."""
        pass

    def equity_series(self) -> pd.Series:
        """Return the equity curve as a pandas Series (index=timestamp)."""
        pass
