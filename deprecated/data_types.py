from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto


class Resolution(Enum):
    Daily = auto()


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
    def __init__(self, bars):
        self._bars = dict(bars)
        self.time = next(iter(bars.values())).end_time if bars else None

    def __getitem__(self, symbol):
        return self._bars[symbol]

    @property
    def Bars(self):
        return self._bars

    @property
    def bars(self):
        return self._bars

    def get(self, symbol, default=None):
        return self._bars.get(symbol, default)

    def __iter__(self):
        return iter(self._bars)

    def keys(self):
        return self._bars.keys()


