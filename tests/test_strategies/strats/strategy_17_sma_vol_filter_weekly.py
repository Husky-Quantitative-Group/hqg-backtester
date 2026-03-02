"""
Strategy 17: SMA + Volatility Filter - DIA vs SHY
Period: 2012-01-01 to 2019-12-31
Cadence: Weekly
Logic: 20-week SMA on DIA, plus 20-week realized vol.
       If price > SMA AND vol < median historical vol -> DIA 100%
       If price > SMA AND vol >= median -> DIA 50% / SHY 50%
       Else -> SHY 100%
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold
from collections import deque
import math

START_DATE = "2012-01-01"
END_DATE = "2019-12-31"

SMA_WINDOW = 20


class SMAVolFilter_DIA_Weekly(Strategy):
    def __init__(self):
        self._prices = deque(maxlen=SMA_WINDOW)
        self._vol_history: list[float] = []
        self._initialized = False

    universe = ["DIA", "SHY"]
    cadence = Cadence(bar_size=BarSize.WEEKLY)

    def _realized_vol(self) -> float | None:
        if len(self._prices) < SMA_WINDOW:
            return None
        prices = list(self._prices)
        rets = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
        mean_r = sum(rets) / len(rets)
        var = sum((r - mean_r) ** 2 for r in rets) / len(rets)
        return math.sqrt(var)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        price = data.close("DIA")
        if price is None:
            return Hold()

        self._prices.append(price)

        if len(self._prices) < SMA_WINDOW:
            if not self._initialized:
                self._initialized = True
                return TargetWeights({"SHY": 1.0})
            return Hold()

        sma = sum(self._prices) / SMA_WINDOW
        vol = self._realized_vol()

        if vol is not None:
            self._vol_history.append(vol)

        # Median vol
        if len(self._vol_history) < 2:
            median_vol = vol if vol else 0
        else:
            sorted_vols = sorted(self._vol_history)
            mid = len(sorted_vols) // 2
            median_vol = sorted_vols[mid]

        if price > sma:
            if vol is not None and vol < median_vol:
                return TargetWeights({"DIA": 1.0})
            else:
                return TargetWeights({"DIA": 0.5, "SHY": 0.5})
        else:
            return TargetWeights({"SHY": 1.0})

