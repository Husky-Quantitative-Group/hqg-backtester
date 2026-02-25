"""
Strategy 16: Rate-of-Change Ranking – Top 2 of 5 asset classes
Period: 2005-01-01 to 2024-12-31
Cadence: Monthly
Logic: Compute 6-month rate of change for SPY, EFA, EEM, TLT, GLD.
       Hold equal weight in the top 2.
       If neither has positive ROC, hold SHY.
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize
from collections import deque

START_DATE = "2005-01-01"
END_DATE = "2024-12-31"

ASSETS = ["SPY", "EFA", "EEM", "TLT", "GLD"]
LOOKBACK = 6


class ROCRankingTop2Monthly(Strategy):
    def __init__(self):
        self._history: dict[str, deque] = {
            t: deque(maxlen=LOOKBACK + 1) for t in ASSETS
        }

    def universe(self) -> list[str]:
        return ASSETS + ["SHY"]

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.MONTHLY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        for t in ASSETS:
            p = data.close(t)
            if p is not None:
                self._history[t].append(p)

        ready = [t for t in ASSETS if len(self._history[t]) == LOOKBACK + 1]
        if not ready:
            return {"SHY": 1.0}

        roc = {}
        for t in ready:
            h = self._history[t]
            roc[t] = (h[-1] / h[0]) - 1.0

        ranked = sorted(roc.items(), key=lambda x: x[1], reverse=True)
        top2 = [(t, r) for t, r in ranked[:2] if r > 0]

        if not top2:
            return {"SHY": 1.0}

        w = 1.0 / 2.0
        weights: dict[str, float] = {t: w for t, _ in top2}

        remaining = 1.0 - sum(weights.values())
        if remaining > 0.001:
            weights["SHY"] = remaining

        return weights
