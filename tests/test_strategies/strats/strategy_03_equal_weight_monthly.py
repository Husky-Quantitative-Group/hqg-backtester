"""
Strategy 03: Equal Weight Buy & Hold - 4 ETFs
Period: 2015-01-01 to 2020-12-31
Cadence: Monthly
Logic: Equal weight SPY, EFA, TLT, GLD. Rebalance monthly.
        (GLD started 2004, so pre-2004 bars will show None for GLD -
         strategy redistributes among available assets.)
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold

START_DATE = "2015-01-01"
END_DATE = "2020-12-31"

TICKERS = ["SPY", "EFA", "TLT", "GLD"]


class EqualWeightMonthly(Strategy):
    universe = ["SPY", "EFA", "TLT", "GLD"]
    cadence = Cadence(bar_size=BarSize.MONTHLY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        available = [t for t in TICKERS if data.close(t) is not None]
        if not available:
            return Hold()

        w = 1.0 / len(available)
        return TargetWeights({t: w for t in available})

