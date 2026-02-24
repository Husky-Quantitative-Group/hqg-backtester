"""
QC Strategy 16: Rate-of-Change Ranking – Top 2 of 5 asset classes
Period: 2005-01-01 to 2024-12-31
Cadence: Monthly
Logic: Compute 6-month ROC for SPY, EFA, EEM, TLT, GLD.
       Hold equal weight in the top 2.
       If neither has positive ROC, hold SHY.
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque


ASSETS = ["SPY", "EFA", "EEM", "TLT", "GLD"]
LOOKBACK = 6


class ROCRankingTop2Monthly(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2005, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self._symbols = {}
        for t in ASSETS:
            self._symbols[t] = self.add_equity(t, Resolution.DAILY).symbol
        self._symbols["SHY"] = self.add_equity("SHY", Resolution.DAILY).symbol

        self._history = {t: deque(maxlen=LOOKBACK + 1) for t in ASSETS}

        self.schedule.on(
            self.date_rules.month_start("SPY"),
            self.time_rules.after_market_open("SPY", 30),
            self._rebalance,
        )

    def on_data(self, data):
        for t in ASSETS:
            sym = self._symbols[t]
            if data.bars.contains_key(sym):
                self._history[t].append(data.bars[sym].close)

    def _rebalance(self):
        ready = [t for t in ASSETS if len(self._history[t]) == LOOKBACK + 1]
        if not ready:
            if not self.portfolio.invested:
                self.set_holdings(self._symbols["SHY"], 1.0)
            return

        roc = {}
        for t in ready:
            h = self._history[t]
            roc[t] = (h[-1] / h[0]) - 1.0

        ranked = sorted(roc.items(), key=lambda x: x[1], reverse=True)
        top2 = [(t, r) for t, r in ranked[:2] if r > 0]

        all_tickers = ASSETS + ["SHY"]

        if not top2:
            for t in ASSETS:
                if self.portfolio[self._symbols[t]].invested:
                    self.liquidate(self._symbols[t])
            self.set_holdings(self._symbols["SHY"], 1.0)
            return

        w = 1.0 / 2.0
        targets = {t: w for t, _ in top2}

        remaining = 1.0 - sum(targets.values())
        if remaining > 0.001:
            targets["SHY"] = remaining

        for t in all_tickers:
            if t in targets:
                self.set_holdings(self._symbols[t], targets[t])
            elif self.portfolio[self._symbols[t]].invested:
                self.liquidate(self._symbols[t])
