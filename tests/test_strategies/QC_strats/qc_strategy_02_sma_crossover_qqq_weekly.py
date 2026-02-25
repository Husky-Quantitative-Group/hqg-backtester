"""
QC Strategy 02: SMA Crossover – QQQ vs AGG
Period: 2005-01-01 to 2015-12-31
Cadence: Weekly
Logic: 10-week SMA vs 30-week SMA on QQQ. If fast > slow, hold QQQ; else hold AGG.
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque


class SMACrossoverQQQ_Weekly(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2005, 1, 1)
        self.set_end_date(2015, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self.qqq = self.add_equity("QQQ", Resolution.DAILY).symbol
        self.agg = self.add_equity("AGG", Resolution.DAILY).symbol

        self._fast_len = 10
        self._slow_len = 30
        self._prices = deque(maxlen=self._slow_len)

        self.schedule.on(
            self.date_rules.week_start("QQQ"),
            self.time_rules.after_market_open("QQQ", 30),
            self._rebalance,
        )

    def on_data(self, data):
        if data.bars.contains_key(self.qqq):
            self._prices.append(data.bars[self.qqq].close)

    def _rebalance(self):
        if len(self._prices) < self._slow_len:
            if not self.portfolio.invested:
                self.set_holdings(self.agg, 1.0)
            return

        prices_list = list(self._prices)
        fast_sma = sum(prices_list[-self._fast_len:]) / self._fast_len
        slow_sma = sum(prices_list) / self._slow_len

        if fast_sma > slow_sma:
            if not self.portfolio[self.qqq].invested or self.portfolio[self.agg].invested:
                self.liquidate(self.agg)
                self.set_holdings(self.qqq, 1.0)
        else:
            if not self.portfolio[self.agg].invested or self.portfolio[self.qqq].invested:
                self.liquidate(self.qqq)
                self.set_holdings(self.agg, 1.0)
