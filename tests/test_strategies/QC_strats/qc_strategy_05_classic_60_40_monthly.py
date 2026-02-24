"""
QC Strategy 05: Classic 60/40 – SPY / TLT
Period: 2002-07-01 to 2025-12-31
Cadence: Monthly
Logic: Hold 60% SPY, 40% TLT. Rebalance monthly.
No shorting. No fees.
"""
from AlgorithmImports import *


class Classic6040Monthly(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2002, 7, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        self.tlt = self.add_equity("TLT", Resolution.DAILY).symbol

        self.schedule.on(
            self.date_rules.month_start("SPY"),
            self.time_rules.after_market_open("SPY", 30),
            self._rebalance,
        )

    def on_data(self, data):
        pass

    def _rebalance(self):
        spy_ok = self.securities[self.spy].price > 0
        tlt_ok = self.securities[self.tlt].price > 0

        if spy_ok and tlt_ok:
            self.set_holdings(self.spy, 0.6)
            self.set_holdings(self.tlt, 0.4)
        elif spy_ok:
            self.set_holdings(self.spy, 1.0)
            self.liquidate(self.tlt)
        elif tlt_ok:
            self.set_holdings(self.tlt, 1.0)
            self.liquidate(self.spy)
