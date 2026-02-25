"""
Strategy 01: Simple Momentum – SPY vs BND
Period: 2010-01-01 to 2020-12-31
Cadence: Daily
Logic: If SPY 20-day return > 0, hold SPY; else hold BND.
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize
from collections import deque

START_DATE = "2010-01-01"
END_DATE = "2020-12-31"


class MomentumSPYBND_Daily(Strategy):
    def __init__(self):
        self._lookback = 20
        self._prices = deque(maxlen=self._lookback + 1)

    def universe(self) -> list[str]:
        return ["SPY", "BND"]

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        price = data.close("SPY")
        if price is None:
            return None

        self._prices.append(price)

        if len(self._prices) < self._lookback + 1:
            return {"BND": 1.0}

        momentum = (self._prices[-1] / self._prices[0]) - 1.0

        if momentum > 0:
            return {"SPY": 1.0}
        else:
            return {"BND": 1.0}
