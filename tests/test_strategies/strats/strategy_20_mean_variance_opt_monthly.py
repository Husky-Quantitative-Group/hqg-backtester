"""
Strategy 20: Mean-Variance Optimization (3 assets, long-only) – SPY, TLT, GLD
Period: 2007-01-01 to 2023-12-31
Cadence: Monthly
Logic: Trailing 12-month returns to estimate expected returns and covariance.
       Solve for max-Sharpe portfolio (long-only) via grid search over weight simplex.
       Risk-free rate assumed 0 for simplicity.
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize
from collections import deque
import math

START_DATE = "2007-01-01"
END_DATE = "2023-12-31"

TICKERS = ["SPY", "TLT", "GLD"]
LOOKBACK = 12


class MeanVarianceOpt3Asset_Monthly(Strategy):
    def __init__(self):
        self._history: dict[str, deque] = {
            t: deque(maxlen=LOOKBACK + 1) for t in TICKERS
        }

    def universe(self) -> list[str]:
        return TICKERS

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.MONTHLY)

    def _compute_returns(self, ticker: str) -> list[float] | None:
        h = list(self._history[ticker])
        if len(h) < LOOKBACK + 1:
            return None
        return [math.log(h[i] / h[i - 1]) for i in range(1, len(h))]

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        for t in TICKERS:
            p = data.close(t)
            if p is not None:
                self._history[t].append(p)

        # Get returns for all assets
        returns_dict = {}
        for t in TICKERS:
            r = self._compute_returns(t)
            if r is None:
                return {"SPY": 0.34, "TLT": 0.33, "GLD": 0.33}
            returns_dict[t] = r

        n = len(returns_dict[TICKERS[0]])

        # Expected returns
        mu = {t: sum(returns_dict[t]) / n for t in TICKERS}

        # Covariance matrix
        cov = {}
        for i, t1 in enumerate(TICKERS):
            for j, t2 in enumerate(TICKERS):
                mu1, mu2 = mu[t1], mu[t2]
                c = sum(
                    (returns_dict[t1][k] - mu1) * (returns_dict[t2][k] - mu2)
                    for k in range(n)
                ) / n
                cov[(t1, t2)] = c

        # Grid search for max Sharpe (long-only, weights sum to 1)
        best_sharpe = -1e10
        best_w = {t: 1.0 / len(TICKERS) for t in TICKERS}
        step = 0.05

        w0_range = [i * step for i in range(int(1.0 / step) + 1)]
        for w0 in w0_range:
            for w1 in w0_range:
                w2 = 1.0 - w0 - w1
                if w2 < -0.001:
                    continue
                w2 = max(0.0, w2)

                ws = [w0, w1, w2]

                port_ret = sum(ws[i] * mu[TICKERS[i]] for i in range(3))
                port_var = sum(
                    ws[i] * ws[j] * cov[(TICKERS[i], TICKERS[j])]
                    for i in range(3)
                    for j in range(3)
                )

                if port_var <= 0:
                    continue

                sharpe = port_ret / math.sqrt(port_var)

                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_w = {TICKERS[i]: ws[i] for i in range(3)}

        # Filter out zero weights
        result = {t: w for t, w in best_w.items() if w > 0.001}
        if not result:
            return {"SPY": 0.34, "TLT": 0.33, "GLD": 0.33}

        return result
