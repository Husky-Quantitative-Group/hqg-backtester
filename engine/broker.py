from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import pandas as pd

@dataclass
class Order:
    side: str                 # "BUY" | "SELL" | "LIQUIDATE"
    symbol: Optional[str]
    qty: int
    submitted_ts: Optional[object] = None

class Broker:
    def __init__(self, fill_rule: str, commission_per_order: float, merged: pd.DataFrame):
        """
        Keep fill semantics, commission, and reference to the merged table
        with MultiIndex COLUMNS so we can price fills from (symbol,'open') at ts.
        """
        pass

    def set_submission_ts(self, ts) -> None:
        """Mark current timestamp; orders placed now will target the next bar's open."""
        pass

    def submit_order(self, side: str, symbol: Optional[str], qty: int) -> None:
        """Queue an order during this bar; engine will schedule/fill it."""
        pass

    def fill_open(self, ts, portfolio) -> None:
        """Execute all orders scheduled for this bar's open and log fills (use merged[(symbol,'open')].loc[ts])."""
        pass

    def _fill(self, ts, symbol: str, qty_signed: int, portfolio) -> None:
        """Apply a single fill at open, charge fee, update portfolio, append trade log."""
        pass

# Suggested helpers:
# - _next_ts_after(ts) -> next timestamp or None  (from merged.index)
# - _open_price(merged, ts, symbol) -> float
