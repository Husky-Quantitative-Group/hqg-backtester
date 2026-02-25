"""
Strategy 05: Classic 60/40 – SPY / TLT
Period: 2002-07-01 to 2025-12-31
Cadence: Monthly
Logic: Hold 60% SPY, 40% TLT. Rebalance monthly.
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize

START_DATE = "2002-07-01"
END_DATE = "2025-12-31"


class Classic6040Monthly(Strategy):
    def universe(self) -> list[str]:
        return ["SPY", "TLT"]

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.MONTHLY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        spy = data.close("SPY")
        tlt = data.close("TLT")

        if spy is None or tlt is None:
            # hold whichever is available
            if spy is not None:
                return {"SPY": 1.0}
            if tlt is not None:
                return {"TLT": 1.0}
            return None

        return {"SPY": 0.6, "TLT": 0.4}
