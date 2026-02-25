"""
QC Strategy 18: All-Weather Inspired – Fixed allocation
Period: 2015-01-01 to 2025-12-31
Cadence: Quarterly
Logic: 30% SPY, 40% TLT, 15% IEF, 7.5% GLD, 7.5% DBC
       Rebalance quarterly. Redistribute if asset unavailable.
No shorting. No fees.
"""
from AlgorithmImports import *


TARGET = {
    "SPY": 0.30,
    "TLT": 0.40,
    "IEF": 0.15,
    "GLD": 0.075,
    "DBC": 0.075,
}


class AllWeatherQuarterly(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2015, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self._symbols = {}
        for t in TARGET:
            self._symbols[t] = self.add_equity(t, Resolution.DAILY).symbol

        self._quarter_count = 0

        self.schedule.on(
            self.date_rules.month_start("SPY"),
            self.time_rules.after_market_open("SPY", 30),
            self._on_month_start,
        )

    def on_data(self, data):
        pass

    def _on_month_start(self):
        self._quarter_count += 1
        if self._quarter_count % 3 != 1:
            return

        available = {
            t: w
            for t, w in TARGET.items()
            if self.securities[self._symbols[t]].price > 0
        }

        if not available:
            return

        total = sum(available.values())
        for t in TARGET:
            if t in available:
                self.set_holdings(self._symbols[t], available[t] / total)
            elif self.portfolio[self._symbols[t]].invested:
                self.liquidate(self._symbols[t])
