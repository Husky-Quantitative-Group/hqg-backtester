"""
QC Strategy 07: Sector Rotation Momentum – Top 3 of 9 sector ETFs
Period: 2014-01-01 to 2024-12-31
Cadence: Monthly
Logic: Track 3-month momentum across 9 SPDR sector ETFs.
       Hold equal weight in the top 3 performers.
       If fewer than 3 have positive momentum, fill remainder with BND.
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque


SECTORS = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB"]
LOOKBACK = 3  # months


class SectorRotationMomentumMonthly(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2014, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self._symbols = {}
        for t in SECTORS:
            self._symbols[t] = self.add_equity(t, Resolution.DAILY).symbol
        self._symbols["BND"] = self.add_equity("BND", Resolution.DAILY).symbol

        self._history = {t: deque(maxlen=LOOKBACK + 1) for t in SECTORS}

        self.schedule.on(
            self.date_rules.month_start("SPY"),
            self.time_rules.after_market_open("SPY", 30),
            self._rebalance,
        )

    def on_data(self, data):
        for t in SECTORS:
            sym = self._symbols[t]
            if data.bars.contains_key(sym):
                self._history[t].append(data.bars[sym].close)

    def _rebalance(self):
        ready = [t for t in SECTORS if len(self._history[t]) == LOOKBACK + 1]

        if not ready:
            if not self.portfolio.invested:
                self.set_holdings(self._symbols["BND"], 1.0)
            return

        mom = {}
        for t in ready:
            h = self._history[t]
            mom[t] = (h[-1] / h[0]) - 1.0

        ranked = sorted(mom.items(), key=lambda x: x[1], reverse=True)
        top3 = [(t, m) for t, m in ranked[:3] if m > 0]

        if not top3:
            self.liquidate()
            self.set_holdings(self._symbols["BND"], 1.0)
            return

        w = 1.0 / 3.0
        targets = {}
        for t, _ in top3:
            targets[t] = w

        remaining = 1.0 - sum(targets.values())
        if remaining > 0.001:
            targets["BND"] = remaining

        # Liquidate anything not in targets
        all_tickers = SECTORS + ["BND"]
        for t in all_tickers:
            if t not in targets and self.portfolio[self._symbols[t]].invested:
                self.liquidate(self._symbols[t])

        for t, wt in targets.items():
            self.set_holdings(self._symbols[t], wt)
