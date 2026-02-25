"""
QC Strategy 14: Trend Following with Trailing High – SPY vs AGG
Period: 2008-01-01 to 2018-12-31
Cadence: Daily
Logic: Track SPY's 252-day high.
       If current price >= 95% of 252-day high → SPY 100%
       Else → AGG 100%
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque


class TrendFollowTrailingHigh_Daily(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2008, 1, 1)
        self.set_end_date(2018, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        self.agg = self.add_equity("AGG", Resolution.DAILY).symbol

        self._window = 252
        self._prices = deque(maxlen=self._window)
        self._initialized = False

    def on_data(self, data):
        if not data.bars.contains_key(self.spy):
            return

        price = data.bars[self.spy].close
        self._prices.append(price)

        if len(self._prices) < self._window:
            if not self._initialized:
                self._initialized = True
                self.set_holdings(self.agg, 1.0)
            return

        high_252 = max(self._prices)
        threshold = 0.95 * high_252

        if price >= threshold:
            if not self.portfolio[self.spy].invested:
                self.liquidate(self.agg)
                self.set_holdings(self.spy, 1.0)
        else:
            if not self.portfolio[self.agg].invested:
                self.liquidate(self.spy)
                self.set_holdings(self.agg, 1.0)
