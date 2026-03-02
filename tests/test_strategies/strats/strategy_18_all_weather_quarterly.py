"""
Strategy 18: All-Weather Inspired - Fixed allocation
Period: 2015-01-01 to 2025-12-31
Cadence: Quarterly
Logic: Inspired by Bridgewater All-Weather:
       30% SPY, 40% TLT, 15% IEF, 7.5% GLD, 7.5% DBC
       Rebalance quarterly. Redistribute if asset unavailable.
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold

START_DATE = "2015-01-01"
END_DATE = "2025-12-31"

TARGET = {
    "SPY": 0.30,
    "TLT": 0.40,
    "IEF": 0.15,
    "GLD": 0.075,
    "DBC": 0.075,
}


class AllWeatherQuarterly(Strategy):
    universe = ["SPY", "TLT", "IEF", "GLD", "DBC"]
    cadence = Cadence(bar_size=BarSize.QUARTERLY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        available = {t: w for t, w in TARGET.items() if data.close(t) is not None}
        if not available:
            return Hold()

        total = sum(available.values())
        return TargetWeights({t: w / total for t, w in available.items()})

