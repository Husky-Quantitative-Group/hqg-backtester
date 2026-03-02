"""
Strategy 14: Trend Following with Trailing High - SPY vs AGG
Period: 2008-01-01 to 2018-12-31
Cadence: Daily
Logic: Track SPY's 52-week (252-day) high.
       If current price >= 95% of 252-day high -> uptrend -> SPY 100%
       Else -> downtrend -> AGG 100%
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold
from collections import deque

START_DATE = "2008-01-01"
END_DATE = "2018-12-31"


class TrendFollowTrailingHigh_Daily(Strategy):
    def __init__(self):
        self._window = 252
        self._prices = deque(maxlen=self._window)
        self._initialized = False

    universe = ["SPY", "AGG"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        price = data.close("SPY")
        if price is None:
            return Hold()

        self._prices.append(price)

        if len(self._prices) < self._window:
            if not self._initialized:
                self._initialized = True
                return TargetWeights({"AGG": 1.0})
            return Hold()

        high_252 = max(self._prices)
        threshold = 0.95 * high_252

        if price >= threshold:
            return TargetWeights({"SPY": 1.0})
        else:
            return TargetWeights({"AGG": 1.0})

