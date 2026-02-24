"""
QC Strategy 11: Golden Cross / Death Cross – IWM vs TLT
Period: 2003-01-01 to 2020-12-31
Cadence: Daily
Logic: 50-day SMA vs 200-day SMA on IWM.
       Golden cross (50 > 200) → IWM 100%
       Death cross (50 < 200) → TLT 100%
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque


class GoldenCrossIWM_Daily(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2003, 1, 1)
        self.set_end_date(2020, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self.iwm = self.add_equity("IWM", Resolution.DAILY).symbol
        self.tlt = self.add_equity("TLT", Resolution.DAILY).symbol

        self._prices = deque(maxlen=200)
        self._initialized = False

    def on_data(self, data):
        if not data.bars.contains_key(self.iwm):
            return

        price = data.bars[self.iwm].close
        self._prices.append(price)

        if len(self._prices) < 200:
            if not self._initialized:
                self._initialized = True
                self.set_holdings(self.tlt, 1.0)
            return

        prices = list(self._prices)
        sma50 = sum(prices[-50:]) / 50
        sma200 = sum(prices) / 200

        if sma50 > sma200:
            if not self.portfolio[self.iwm].invested:
                self.liquidate(self.tlt)
                self.set_holdings(self.iwm, 1.0)
        else:
            if not self.portfolio[self.tlt].invested:
                self.liquidate(self.iwm)
                self.set_holdings(self.tlt, 1.0)
