"""
QC Strategy 13: Absolute Momentum – Tech Stocks with Cash Filter
Period: 2010-01-01 to 2026-01-01
Cadence: Monthly
Logic: Track 12-month momentum on AAPL, MSFT, GOOG, AMZN.
       Hold equal weight across those with positive 12-month momentum.
       If none are positive, hold SHY (cash proxy).
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque


TICKERS = ["AAPL", "MSFT", "GOOG", "AMZN"]
LOOKBACK = 12  # months


class AbsMomentumTechMonthly(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2010, 1, 1)
        self.set_end_date(2026, 1, 1)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self._symbols = {}
        for t in TICKERS:
            self._symbols[t] = self.add_equity(t, Resolution.DAILY).symbol
        self._symbols["SHY"] = self.add_equity("SHY", Resolution.DAILY).symbol

        self._history = {t: deque(maxlen=LOOKBACK + 1) for t in TICKERS}

        self.schedule.on(
            self.date_rules.month_start("AAPL"),
            self.time_rules.after_market_open("AAPL", 30),
            self._rebalance,
        )

    def on_data(self, data):
        for t in TICKERS:
            sym = self._symbols[t]
            if data.bars.contains_key(sym):
                self._history[t].append(data.bars[sym].close)

    def _rebalance(self):
        ready = [t for t in TICKERS if len(self._history[t]) == LOOKBACK + 1]

        if not ready:
            if not self.portfolio.invested:
                self.set_holdings(self._symbols["SHY"], 1.0)
            return

        positive = []
        for t in ready:
            h = self._history[t]
            mom = (h[-1] / h[0]) - 1.0
            if mom > 0:
                positive.append(t)

        all_tickers = TICKERS + ["SHY"]

        if not positive:
            for t in TICKERS:
                if self.portfolio[self._symbols[t]].invested:
                    self.liquidate(self._symbols[t])
            self.set_holdings(self._symbols["SHY"], 1.0)
            return

        w = 1.0 / len(positive)
        for t in all_tickers:
            if t in positive:
                self.set_holdings(self._symbols[t], w)
            elif self.portfolio[self._symbols[t]].invested:
                self.liquidate(self._symbols[t])
