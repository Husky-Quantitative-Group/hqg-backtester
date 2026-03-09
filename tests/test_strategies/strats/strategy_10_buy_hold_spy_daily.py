"""
Strategy 10: Buy & Hold SPY (Baseline)
Period: 2000-01-01 to 2026-01-01
Cadence: Daily
Logic: 100% SPY at all times. Simplest possible strategy for baseline comparison.
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold

START_DATE = "2000-01-01"
END_DATE = "2026-01-01"


class BuyAndHoldSPY_Daily(Strategy):
    def __init__(self):
        self._entered = False

    universe = ["SPY"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        if data.close("SPY") is None:
            return Hold()

        if not self._entered:
            self._entered = True
            return TargetWeights({"SPY": 1.0})

        return Hold()  # No rebalance needed

