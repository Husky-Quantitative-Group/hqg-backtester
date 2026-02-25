"""
QC Strategy 10: Buy & Hold SPY (Baseline)
Period: 2000-01-01 to 2026-01-01
Cadence: Daily
Logic: 100% SPY at all times. Simplest possible strategy for baseline comparison.
No shorting. No fees.
"""
from AlgorithmImports import *


class BuyAndHoldSPY_Daily(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2000, 1, 1)
        self.set_end_date(2026, 1, 1)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        self._entered = False

    def on_data(self, data):
        if not self._entered and data.bars.contains_key(self.spy):
            self.set_holdings(self.spy, 1.0)
            self._entered = True
