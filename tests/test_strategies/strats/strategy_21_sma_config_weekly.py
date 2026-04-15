"""
Strategy 21: SMA Crossover with config-injected window sizes - QQQ vs AGG
Period: 2015-01-01 to 2020-12-31
Cadence: Weekly
Logic: fast_period-week SMA vs slow_period-week SMA on QQQ. If fast > slow, hold QQQ; else hold AGG.
Params: fast_period, slow_period injected via config module (used in simulations/sweeps).
"""
import config
from collections import deque
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold

START_DATE = "2015-01-01"
END_DATE = "2020-12-31"


class SMAConfigWeekly(Strategy):
    def __init__(self):
        self._fast_len = config.fast_period
        self._slow_len = config.slow_period
        self._prices = deque(maxlen=self._slow_len)

    universe = ["QQQ", "AGG"]
    cadence = Cadence(bar_size=BarSize.WEEKLY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        price = data.close("QQQ")
        if price is None:
            return Hold()

        self._prices.append(price)

        if len(self._prices) < self._slow_len:
            return TargetWeights({"AGG": 1.0})

        prices_list = list(self._prices)
        fast_sma = sum(prices_list[-self._fast_len:]) / self._fast_len
        slow_sma = sum(prices_list) / self._slow_len

        if fast_sma > slow_sma:
            return TargetWeights({"QQQ": 1.0})
        else:
            return TargetWeights({"AGG": 1.0})
