"""
Strategy 07: Sector Rotation Momentum - Top 3 of 9 sector ETFs
Period: 2014-01-01 to 2024-12-31
Cadence: Monthly
Logic: Track 3-month momentum across 9 SPDR sector ETFs.
       Hold equal weight in the top 3 performers.
       If fewer than 3 have positive momentum, fill remainder with BND.
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold
from collections import deque

START_DATE = "2014-01-01"
END_DATE = "2024-12-31"

SECTORS = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB"]
LOOKBACK = 3  # months


class SectorRotationMomentumMonthly(Strategy):
    def __init__(self):
        self._history: dict[str, deque] = {
            t: deque(maxlen=LOOKBACK + 1) for t in SECTORS
        }

    universe = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "BND"]
    cadence = Cadence(bar_size=BarSize.MONTHLY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        # Collect prices
        for t in SECTORS:
            p = data.close(t)
            if p is not None:
                self._history[t].append(p)

        # Need full lookback for momentum calc
        ready = [
            t for t in SECTORS if len(self._history[t]) == LOOKBACK + 1
        ]

        if not ready:
            return TargetWeights({"BND": 1.0})

        # Compute momentum
        mom = {}
        for t in ready:
            h = self._history[t]
            mom[t] = (h[-1] / h[0]) - 1.0

        # Sort descending by momentum, pick top 3
        ranked = sorted(mom.items(), key=lambda x: x[1], reverse=True)
        top3 = [(t, m) for t, m in ranked[:3] if m > 0]

        if not top3:
            return TargetWeights({"BND": 1.0})

        w = 1.0 / 3.0
        weights: dict[str, float] = {}
        for t, _ in top3:
            weights[t] = w

        # Remaining weight goes to BND
        remaining = 1.0 - sum(weights.values())
        if remaining > 0.001:
            weights["BND"] = remaining

        return TargetWeights(weights)

