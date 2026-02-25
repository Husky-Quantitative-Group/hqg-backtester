"""
QC Strategy 12: Three-Fund Portfolio – VTI / VXUS / BND
Period: 2014-01-01 to 2025-12-31
Cadence: Quarterly
Logic: 50% VTI, 30% VXUS, 20% BND. Rebalance quarterly.
No shorting. No fees.
"""
from AlgorithmImports import *


TARGET = {"VTI": 0.50, "VXUS": 0.30, "BND": 0.20}


class ThreeFundQuarterly(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2014, 1, 1)
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
            self.date_rules.month_start("VTI"),
            self.time_rules.after_market_open("VTI", 30),
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
