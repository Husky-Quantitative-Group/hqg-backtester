"""
QC Strategy 03: Equal Weight Buy & Hold – 4 ETFs
Period: 2015-01-01 to 2020-12-31
Cadence: Monthly
Logic: Equal weight SPY, EFA, TLT, GLD. Rebalance monthly.
       Redistribute among available assets if one is missing.
No shorting. No fees.
"""
from AlgorithmImports import *


TICKERS = ["SPY", "EFA", "TLT", "GLD"]


class EqualWeightMonthly(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2015, 1, 1)
        self.set_end_date(2020, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self._symbols = {}
        for t in TICKERS:
            self._symbols[t] = self.add_equity(t, Resolution.DAILY).symbol

        self.schedule.on(
            self.date_rules.month_start("SPY"),
            self.time_rules.after_market_open("SPY", 30),
            self._rebalance,
        )

    def on_data(self, data):
        pass

    def _rebalance(self):
        available = [
            t for t in TICKERS
            if self.securities[self._symbols[t]].has_data
            and self.securities[self._symbols[t]].price > 0
        ]

        if not available:
            return

        for t in TICKERS:
            if t not in available and self.portfolio[self._symbols[t]].invested:
                self.liquidate(self._symbols[t])

        w = 1.0 / len(available)
        for t in available:
            self.set_holdings(self._symbols[t], w)
