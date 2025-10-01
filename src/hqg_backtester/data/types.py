from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Dict, Iterable, Iterator, Mapping, Optional


class Resolution(Enum):
    Daily = auto()
    # Hour = auto()
    # Minute = auto()


@dataclass
class TradeBar:
    symbol: str
    end_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class Slice:
    """Dict-like container mapping symbol -> TradeBar for a single time step."""

    def __init__(self, bars: Mapping[str, TradeBar]):
        self._bars: Dict[str, TradeBar] = dict(bars)
        # Set time from the first trade bar if available
        self.time = next(iter(bars.values())).end_time if bars else None

    def __getitem__(self, symbol: str) -> TradeBar:
        return self._bars[symbol]

    @property
    def Bars(self) -> Mapping[str, TradeBar]:
        return self._bars
    
    @property
    def trade_bars(self) -> Mapping[str, TradeBar]:
        """Alias for Bars to match strategy expectations."""
        return self._bars

    def get(self, symbol: str, default: Optional[TradeBar] = None) -> Optional[TradeBar]:
        return self._bars.get(symbol, default)

    def __iter__(self) -> Iterator[str]:
        return iter(self._bars)

    def keys(self) -> Iterable[str]:
        return self._bars.keys()


