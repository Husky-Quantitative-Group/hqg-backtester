"""
QC Strategy 01: Simple Momentum – SPY vs BND
Period: 2010-01-01 to 2020-12-31
Cadence: Daily
Logic: If SPY 20-day return > 0, hold SPY; else hold BND.
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque


class MomentumSPYBND_Daily(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2010, 1, 1)
        self.set_end_date(2020, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        self.bnd = self.add_equity("BND", Resolution.DAILY).symbol

        self._lookback = 20
        self._prices = deque(maxlen=self._lookback + 1)

    def on_data(self, data):
        if not data.bars.contains_key(self.spy):
            return

        price = data.bars[self.spy].close
        self._prices.append(price)

        if len(self._prices) < self._lookback + 1:
            if not self.portfolio.invested:
                self.set_holdings(self.bnd, 1.0)
            return

        momentum = (self._prices[-1] / self._prices[0]) - 1.0

        if momentum > 0:
            self.set_holdings(self.spy, 1.0)
            if self.portfolio[self.bnd].invested:
                self.liquidate(self.bnd)
        else:
            self.set_holdings(self.bnd, 1.0)
            if self.portfolio[self.spy].invested:
                self.liquidate(self.spy)
