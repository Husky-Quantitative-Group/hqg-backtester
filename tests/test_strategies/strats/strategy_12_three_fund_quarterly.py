"""
Strategy 12: Three-Fund Portfolio - VTI / VXUS / BND
Period: 2014-01-01 to 2025-12-31
Cadence: Quarterly
Logic: 50% VTI, 30% VXUS, 20% BND. Rebalance quarterly.
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold

START_DATE = "2014-01-01"
END_DATE = "2025-12-31"

TARGET = {"VTI": 0.50, "VXUS": 0.30, "BND": 0.20}


class ThreeFundQuarterly(Strategy):
    universe = ["VTI", "VXUS", "BND"]
    cadence = Cadence(bar_size=BarSize.QUARTERLY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        available = {t: w for t, w in TARGET.items() if data.close(t) is not None}
        if not available:
            return Hold()

        # Redistribute weights if an asset is missing
        total = sum(available.values())
        return TargetWeights({t: w / total for t, w in available.items()})

