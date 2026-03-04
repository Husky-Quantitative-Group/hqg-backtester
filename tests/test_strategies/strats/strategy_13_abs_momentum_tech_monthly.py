"""
Strategy 13: Absolute Momentum - Tech Stocks with Cash Filter
Period: 2010-01-01 to 2026-01-01
Cadence: Monthly
Logic: Track 12-month momentum on AAPL, MSFT, GOOG, AMZN.
       Hold equal weight across those with positive 12-month momentum.
       If none are positive, hold SHY (cash proxy).
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold
from collections import deque

START_DATE = "2010-01-01"
END_DATE = "2026-01-01"

TICKERS = ["AAPL", "MSFT", "GOOG", "AMZN"]
LOOKBACK = 12  # months


class AbsMomentumTechMonthly(Strategy):
    def __init__(self):
        self._history: dict[str, deque] = {
            t: deque(maxlen=LOOKBACK + 1) for t in TICKERS
        }

    universe = ["AAPL", "MSFT", "GOOG", "AMZN", "SHY"]
    cadence = Cadence(bar_size=BarSize.MONTHLY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        for t in TICKERS:
            p = data.close(t)
            if p is not None:
                self._history[t].append(p)

        # Need full lookback
        ready = [t for t in TICKERS if len(self._history[t]) == LOOKBACK + 1]

        if not ready:
            return TargetWeights({"SHY": 1.0})

        # Pick those with positive 12-month momentum
        positive = []
        for t in ready:
            h = self._history[t]
            mom = (h[-1] / h[0]) - 1.0
            if mom > 0:
                positive.append(t)

        if not positive:
            return TargetWeights({"SHY": 1.0})

        w = 1.0 / len(positive)
        return TargetWeights({t: w for t in positive})


