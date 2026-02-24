"""
QC Strategy 04: Dual Momentum – SPY vs EFA, with BND as safe haven
Period: 2013-06-01 to 2023-12-31
Cadence: Quarterly
Logic: Compute 4-quarter return for SPY and EFA.
       If best performer has positive momentum, hold it; else hold BND.
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque


class DualMomentumQuarterly(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2013, 6, 1)
        self.set_end_date(2023, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        self.efa = self.add_equity("EFA", Resolution.DAILY).symbol
        self.bnd = self.add_equity("BND", Resolution.DAILY).symbol

        self._lookback = 4  # quarters
        self._spy_prices = deque(maxlen=self._lookback + 1)
        self._efa_prices = deque(maxlen=self._lookback + 1)
        self._quarter_count = 0

        # Fire quarterly: every 3 months at month start
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

        spy_price = self.securities[self.spy].price
        efa_price = self.securities[self.efa].price

        if spy_price <= 0 or efa_price <= 0:
            if not self.portfolio.invested:
                self.set_holdings(self.bnd, 1.0)
            return

        self._spy_prices.append(spy_price)
        self._efa_prices.append(efa_price)

        if len(self._spy_prices) < self._lookback + 1:
            if not self.portfolio.invested:
                self.set_holdings(self.bnd, 1.0)
            return

        spy_mom = (self._spy_prices[-1] / self._spy_prices[0]) - 1.0
        efa_mom = (self._efa_prices[-1] / self._efa_prices[0]) - 1.0

        if spy_mom >= efa_mom:
            best_sym, best_mom = self.spy, spy_mom
        else:
            best_sym, best_mom = self.efa, efa_mom

        if best_mom > 0:
            self.set_holdings(best_sym, 1.0)
            # Liquidate others
            for s in [self.spy, self.efa, self.bnd]:
                if s != best_sym and self.portfolio[s].invested:
                    self.liquidate(s)
        else:
            self.set_holdings(self.bnd, 1.0)
            for s in [self.spy, self.efa]:
                if self.portfolio[s].invested:
                    self.liquidate(s)
