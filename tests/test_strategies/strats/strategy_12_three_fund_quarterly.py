"""
Strategy 12: Three-Fund Portfolio – VTI / VXUS / BND
Period: 2014-01-01 to 2025-12-31
Cadence: Quarterly
Logic: 50% VTI, 30% VXUS, 20% BND. Rebalance quarterly.
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize

START_DATE = "2014-01-01"
END_DATE = "2025-12-31"

TARGET = {"VTI": 0.50, "VXUS": 0.30, "BND": 0.20}


class ThreeFundQuarterly(Strategy):
    def universe(self) -> list[str]:
        return list(TARGET.keys())

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.QUARTERLY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        available = {t: w for t, w in TARGET.items() if data.close(t) is not None}
        if not available:
            return None

        # Redistribute weights if an asset is missing
        total = sum(available.values())
        return {t: w / total for t, w in available.items()}
