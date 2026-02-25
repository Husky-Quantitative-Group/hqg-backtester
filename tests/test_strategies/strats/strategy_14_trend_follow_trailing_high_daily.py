"""
Strategy 14: Trend Following with Trailing High – SPY vs AGG
Period: 2008-01-01 to 2018-12-31
Cadence: Daily
Logic: Track SPY's 52-week (252-day) high.
       If current price >= 95% of 252-day high → uptrend → SPY 100%
       Else → downtrend → AGG 100%
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize
from collections import deque

START_DATE = "2008-01-01"
END_DATE = "2018-12-31"


class TrendFollowTrailingHigh_Daily(Strategy):
    def __init__(self):
        self._window = 252
        self._prices = deque(maxlen=self._window)
        self._initialized = False

    def universe(self) -> list[str]:
        return ["SPY", "AGG"]

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        price = data.close("SPY")
        if price is None:
            return None

        self._prices.append(price)

        if len(self._prices) < self._window:
            if not self._initialized:
                self._initialized = True
                return {"AGG": 1.0}
            return None

        high_252 = max(self._prices)
        threshold = 0.95 * high_252

        if price >= threshold:
            return {"SPY": 1.0}
        else:
            return {"AGG": 1.0}
