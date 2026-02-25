"""
QC Strategy 19: MACD Signal – QQQ vs BND
Period: 2012-01-01 to 2025-12-31
Cadence: Daily
Logic: Compute MACD (12-day EMA - 26-day EMA) and 9-day signal line on QQQ.
       MACD > signal → QQQ 100%
       MACD <= signal → BND 100%
No shorting. No fees.
"""
from AlgorithmImports import *


class MACDSignalQQQ_Daily(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2012, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self.qqq = self.add_equity("QQQ", Resolution.DAILY).symbol
        self.bnd = self.add_equity("BND", Resolution.DAILY).symbol

        self._ema12 = None
        self._ema26 = None
        self._signal = None
        self._count = 0
        self._mult12 = 2.0 / (12 + 1)
        self._mult26 = 2.0 / (26 + 1)
        self._mult9 = 2.0 / (9 + 1)

    def on_data(self, data):
        if not data.bars.contains_key(self.qqq):
            return

        price = data.bars[self.qqq].close
        self._count += 1

        if self._ema12 is None:
            self._ema12 = price
            self._ema26 = price
            self.set_holdings(self.bnd, 1.0)
            return

        self._ema12 = price * self._mult12 + self._ema12 * (1 - self._mult12)
        self._ema26 = price * self._mult26 + self._ema26 * (1 - self._mult26)

        macd_line = self._ema12 - self._ema26

        if self._count < 26:
            return

        if self._signal is None:
            self._signal = macd_line
            return

        self._signal = macd_line * self._mult9 + self._signal * (1 - self._mult9)

        if self._count < 35:
            return

        if macd_line > self._signal:
            if not self.portfolio[self.qqq].invested:
                self.liquidate(self.bnd)
                self.set_holdings(self.qqq, 1.0)
        else:
            if not self.portfolio[self.bnd].invested:
                self.liquidate(self.qqq)
                self.set_holdings(self.bnd, 1.0)
