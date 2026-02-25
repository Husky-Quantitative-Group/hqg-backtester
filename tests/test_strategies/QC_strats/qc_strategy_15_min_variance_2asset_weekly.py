"""
QC Strategy 15: Minimum Variance (2-asset simplified) – SPY / TLT
Period: 2006-01-01 to 2021-12-31
Cadence: Weekly
Logic: Compute trailing 26-week covariance matrix for SPY and TLT.
       Solve for minimum variance portfolio (long-only, sum to 1).
       w_SPY = (σ²_TLT - σ_SPY_TLT) / (σ²_SPY + σ²_TLT - 2·σ_SPY_TLT)
       Clamp to [0, 1].
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque
import math


LOOKBACK = 26


class MinVariance2Asset_Weekly(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2006, 1, 1)
        self.set_end_date(2021, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        self.tlt = self.add_equity("TLT", Resolution.DAILY).symbol

        self._spy_prices = deque(maxlen=LOOKBACK + 1)
        self._tlt_prices = deque(maxlen=LOOKBACK + 1)

        self.schedule.on(
            self.date_rules.week_start("SPY"),
            self.time_rules.after_market_open("SPY", 30),
            self._rebalance,
        )

    def on_data(self, data):
        if data.bars.contains_key(self.spy):
            self._spy_prices.append(data.bars[self.spy].close)
        if data.bars.contains_key(self.tlt):
            self._tlt_prices.append(data.bars[self.tlt].close)

    def _rebalance(self):
        if len(self._spy_prices) < LOOKBACK + 1 or len(self._tlt_prices) < LOOKBACK + 1:
            self.set_holdings(self.spy, 0.5)
            self.set_holdings(self.tlt, 0.5)
            return

        spy_list = list(self._spy_prices)
        tlt_list = list(self._tlt_prices)

        spy_rets = [math.log(spy_list[i] / spy_list[i - 1]) for i in range(1, len(spy_list))]
        tlt_rets = [math.log(tlt_list[i] / tlt_list[i - 1]) for i in range(1, len(tlt_list))]

        n = len(spy_rets)
        mu_s = sum(spy_rets) / n
        mu_t = sum(tlt_rets) / n

        var_s = sum((r - mu_s) ** 2 for r in spy_rets) / n
        var_t = sum((r - mu_t) ** 2 for r in tlt_rets) / n
        cov_st = sum((spy_rets[i] - mu_s) * (tlt_rets[i] - mu_t) for i in range(n)) / n

        denom = var_s + var_t - 2 * cov_st
        if abs(denom) < 1e-12:
            w_spy = 0.5
        else:
            w_spy = (var_t - cov_st) / denom
            w_spy = max(0.0, min(1.0, w_spy))

        w_tlt = 1.0 - w_spy

        self.set_holdings(self.spy, w_spy)
        self.set_holdings(self.tlt, w_tlt)
