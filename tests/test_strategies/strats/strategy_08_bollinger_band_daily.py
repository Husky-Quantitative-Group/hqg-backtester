"""
Strategy 08: Bollinger Band Mean Reversion - SPY vs SHY
Period: 2015-01-01 to 2025-12-31
Cadence: Daily
Logic: 20-day Bollinger Bands on SPY (2 std dev).
       Price < lower band -> oversold -> SPY 100%
       Price > upper band -> overbought -> SHY 100%
       Otherwise -> SPY 60% / SHY 40%
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold
from collections import deque
import math

START_DATE = "2015-01-01"
END_DATE = "2025-12-31"


class BollingerBandSPY_Daily(Strategy):
    def __init__(self):
        self._window = 20
        self._num_std = 2.0
        self._prices = deque(maxlen=self._window)
        self._initialized = False

    universe = ["SPY", "SHY"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        price = data.close("SPY")
        if price is None:
            return Hold()

        self._prices.append(price)

        if len(self._prices) < self._window:
            if not self._initialized:
                self._initialized = True
                return TargetWeights({"SHY": 1.0})
            return Hold()

        prices = list(self._prices)
        mean = sum(prices) / self._window
        variance = sum((p - mean) ** 2 for p in prices) / self._window
        std = math.sqrt(variance)

        upper = mean + self._num_std * std
        lower = mean - self._num_std * std

        if price < lower:
            return TargetWeights({"SPY": 1.0})
        elif price > upper:
            return TargetWeights({"SHY": 1.0})
        else:
            return TargetWeights({"SPY": 0.6, "SHY": 0.4})

