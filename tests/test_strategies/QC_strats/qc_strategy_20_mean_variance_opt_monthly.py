"""
QC Strategy 20: Mean-Variance Optimization (3 assets, long-only) – SPY, TLT, GLD
Period: 2007-01-01 to 2023-12-31
Cadence: Monthly
Logic: Trailing 12-month returns to estimate expected returns and covariance.
       Solve for max-Sharpe portfolio (long-only) via grid search over weight simplex.
       Risk-free rate assumed 0.
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque
import math


TICKERS = ["SPY", "TLT", "GLD"]
LOOKBACK = 12


class MeanVarianceOpt3Asset_Monthly(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2007, 1, 1)
        self.set_end_date(2023, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self._symbols = {}
        for t in TICKERS:
            self._symbols[t] = self.add_equity(t, Resolution.DAILY).symbol

        self._history = {t: deque(maxlen=LOOKBACK + 1) for t in TICKERS}

        self.schedule.on(
            self.date_rules.month_start("SPY"),
            self.time_rules.after_market_open("SPY", 30),
            self._rebalance,
        )

    def on_data(self, data):
        for t in TICKERS:
            sym = self._symbols[t]
            if data.bars.contains_key(sym):
                self._history[t].append(data.bars[sym].close)

    def _compute_returns(self, ticker):
        h = list(self._history[ticker])
        if len(h) < LOOKBACK + 1:
            return None
        return [math.log(h[i] / h[i - 1]) for i in range(1, len(h))]

    def _rebalance(self):
        returns_dict = {}
        for t in TICKERS:
            r = self._compute_returns(t)
            if r is None:
                self.set_holdings(self._symbols["SPY"], 0.34)
                self.set_holdings(self._symbols["TLT"], 0.33)
                self.set_holdings(self._symbols["GLD"], 0.33)
                return
            returns_dict[t] = r

        n = len(returns_dict[TICKERS[0]])

        mu = {t: sum(returns_dict[t]) / n for t in TICKERS}

        cov = {}
        for t1 in TICKERS:
            for t2 in TICKERS:
                mu1, mu2 = mu[t1], mu[t2]
                c = sum(
                    (returns_dict[t1][k] - mu1) * (returns_dict[t2][k] - mu2)
                    for k in range(n)
                ) / n
                cov[(t1, t2)] = c

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

        result = {t: w for t, w in best_w.items() if w > 0.001}
        if not result:
            result = {"SPY": 0.34, "TLT": 0.33, "GLD": 0.33}

        for t in TICKERS:
            if t in result:
                self.set_holdings(self._symbols[t], result[t])
            elif self.portfolio[self._symbols[t]].invested:
                self.liquidate(self._symbols[t])
