"""
QC Strategy 08: Bollinger Band Mean Reversion – SPY vs SHY
Period: 2015-01-01 to 2025-12-31
Cadence: Daily
Logic: 20-day Bollinger Bands on SPY (2 std dev).
       Price < lower band → SPY 100%
       Price > upper band → SHY 100%
       Otherwise → SPY 60% / SHY 40%
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque
import math


class BollingerBandSPY_Daily(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2015, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        self.shy = self.add_equity("SHY", Resolution.DAILY).symbol

        self._window = 20
        self._num_std = 2.0
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
                self.set_holdings(self.shy, 1.0)
            return

        prices = list(self._prices)
        mean = sum(prices) / self._window
        variance = sum((p - mean) ** 2 for p in prices) / self._window
        std = math.sqrt(variance)

        upper = mean + self._num_std * std
        lower = mean - self._num_std * std

        if price < lower:
            self.set_holdings(self.spy, 1.0)
            if self.portfolio[self.shy].invested:
                self.liquidate(self.shy)
        elif price > upper:
            self.set_holdings(self.shy, 1.0)
            if self.portfolio[self.spy].invested:
                self.liquidate(self.spy)
        else:
            self.set_holdings(self.spy, 0.6)
            self.set_holdings(self.shy, 0.4)
