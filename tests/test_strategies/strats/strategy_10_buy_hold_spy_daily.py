"""
Strategy 10: Buy & Hold SPY (Baseline)
Period: 2000-01-01 to 2026-01-01
Cadence: Daily
Logic: 100% SPY at all times. Simplest possible strategy for baseline comparison.
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize

START_DATE = "2000-01-01"
END_DATE = "2026-01-01"


class BuyAndHoldSPY_Daily(Strategy):
    def __init__(self):
        self._entered = False

    def universe(self) -> list[str]:
        return ["SPY"]

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        if data.close("SPY") is None:
            return None

        if not self._entered:
            self._entered = True
            return {"SPY": 1.0}

        return None  # No rebalance needed
