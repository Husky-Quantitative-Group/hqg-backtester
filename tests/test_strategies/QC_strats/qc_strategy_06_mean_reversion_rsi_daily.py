"""
QC Strategy 06: Mean Reversion (RSI-like) – AAPL vs BND
Period: 2010-01-01 to 2025-06-30
Cadence: Daily
Logic: Compute 14-day RSI on AAPL.
       RSI < 30 → AAPL 80% / BND 20%
       RSI > 70 → BND 100%
       Otherwise → AAPL 50% / BND 50%
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque


class MeanReversionRSI_Daily(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2010, 1, 1)
        self.set_end_date(2025, 6, 30)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self.aapl = self.add_equity("AAPL", Resolution.DAILY).symbol
        self.bnd = self.add_equity("BND", Resolution.DAILY).symbol

        self._period = 14
        self._prices = deque(maxlen=self._period + 1)
        self._first_trade = True

    def _compute_rsi(self):
        if len(self._prices) < self._period + 1:
            return None

        prices = list(self._prices)
        gains = []
        losses = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(change))

        avg_gain = sum(gains) / self._period
        avg_loss = sum(losses) / self._period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def on_data(self, data):
        if not data.bars.contains_key(self.aapl):
            return

        price = data.bars[self.aapl].close
        self._prices.append(price)
        rsi = self._compute_rsi()

        if rsi is None:
            if self._first_trade:
                self._first_trade = False
                self.set_holdings(self.bnd, 1.0)
            return

        self._first_trade = False

        if rsi < 30:
            self.set_holdings(self.aapl, 0.8)
            self.set_holdings(self.bnd, 0.2)
        elif rsi > 70:
            self.set_holdings(self.bnd, 1.0)
            if self.portfolio[self.aapl].invested:
                self.liquidate(self.aapl)
        else:
            self.set_holdings(self.aapl, 0.5)
            self.set_holdings(self.bnd, 0.5)
