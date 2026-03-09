"""
Strategy 11: Golden Cross / Death Cross - IWM vs TLT
Period: 2003-01-01 to 2020-12-31
Cadence: Daily
Logic: 50-day SMA vs 200-day SMA on IWM.
       Golden cross (50 > 200) -> IWM 100%
       Death cross (50 < 200) -> TLT 100%
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold
from collections import deque

START_DATE = "2003-01-01"
END_DATE = "2020-12-31"


class GoldenCrossIWM_Daily(Strategy):
    def __init__(self):
        self._prices = deque(maxlen=200)
        self._initialized = False

    universe = ["IWM", "TLT"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        price = data.close("IWM")
        if price is None:
            return Hold()

        self._prices.append(price)

        if len(self._prices) < 200:
            if not self._initialized:
                self._initialized = True
                return TargetWeights({"TLT": 1.0})
            return Hold()

        prices = list(self._prices)
        sma50 = sum(prices[-50:]) / 50
        sma200 = sum(prices) / 200

        if sma50 > sma200:
            return TargetWeights({"IWM": 1.0})
        else:
            return TargetWeights({"TLT": 1.0})

