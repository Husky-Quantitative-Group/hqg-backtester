from dataclasses import dataclass
from typing import Dict, List, Any
import pandas as pd

@dataclass
class Position:
    qty: int = 0
    avg_price: float = 0.0

class Portfolio:
    def __init__(self, initial_cash: float):
        """Initialize cash, positions map, and minimal history buffer."""
        pass

    def apply_fill(self, symbol: str, qty_signed: int, price: float, fee: float) -> None:
        """Update cash/position for one executed trade; append a simple history row."""
        pass

    def total_equity(self, merged: pd.DataFrame, ts) -> float:
        """
        Return cash + sum(positions * price at ts).
        Price source: merged[(symbol,'close')] if present; fallback to (symbol,'open').
        """
        pass
