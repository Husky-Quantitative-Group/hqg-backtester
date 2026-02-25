"""
Strategy 04: Dual Momentum – SPY vs EFA, with BND as safe haven
Period: 2013-06-01 to 2023-12-31
Cadence: Quarterly
Logic: Compute 12-month (approx 4-quarter) return for SPY and EFA.
       If best performer has positive momentum, hold it; else hold BND.
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize
from collections import deque

START_DATE = "2013-06-01"
END_DATE = "2023-12-31"


class DualMomentumQuarterly(Strategy):
    def __init__(self):
        self._lookback = 4  # 4 quarters ≈ 12 months
        self._spy_prices = deque(maxlen=self._lookback + 1)
        self._efa_prices = deque(maxlen=self._lookback + 1)

    def universe(self) -> list[str]:
        return ["SPY", "EFA", "BND"]

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.QUARTERLY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        spy_price = data.close("SPY")
        efa_price = data.close("EFA")

        if spy_price is None or efa_price is None:
            return {"BND": 1.0}

        self._spy_prices.append(spy_price)
        self._efa_prices.append(efa_price)

        if len(self._spy_prices) < self._lookback + 1:
            return {"BND": 1.0}

        spy_mom = (self._spy_prices[-1] / self._spy_prices[0]) - 1.0
        efa_mom = (self._efa_prices[-1] / self._efa_prices[0]) - 1.0

        # Relative momentum: pick the better performer
        if spy_mom >= efa_mom:
            best_ticker, best_mom = "SPY", spy_mom
        else:
            best_ticker, best_mom = "EFA", efa_mom

        # Absolute momentum: only hold if positive
        if best_mom > 0:
            return {best_ticker: 1.0}
        else:
            return {"BND": 1.0}
