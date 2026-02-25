"""
QC Strategy 17: SMA + Volatility Filter – DIA vs SHY
Period: 2012-01-01 to 2019-12-31
Cadence: Weekly
Logic: 20-week SMA on DIA, plus 20-week realized vol.
       If price > SMA AND vol < median historical vol → DIA 100%
       If price > SMA AND vol >= median → DIA 50% / SHY 50%
       Else → SHY 100%
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque
import math


SMA_WINDOW = 20


class SMAVolFilter_DIA_Weekly(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2012, 1, 1)
        self.set_end_date(2019, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self.dia = self.add_equity("DIA", Resolution.DAILY).symbol
        self.shy = self.add_equity("SHY", Resolution.DAILY).symbol

        self._prices = deque(maxlen=SMA_WINDOW)
        self._vol_history = []
        self._initialized = False

        self.schedule.on(
            self.date_rules.week_start("DIA"),
            self.time_rules.after_market_open("DIA", 30),
            self._rebalance,
        )

    def on_data(self, data):
        if data.bars.contains_key(self.dia):
            self._prices.append(data.bars[self.dia].close)

    def _realized_vol(self):
        if len(self._prices) < SMA_WINDOW:
            return None
        prices = list(self._prices)
        rets = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
        mean_r = sum(rets) / len(rets)
        var = sum((r - mean_r) ** 2 for r in rets) / len(rets)
        return math.sqrt(var)

    def _rebalance(self):
        if len(self._prices) < SMA_WINDOW:
            if not self._initialized:
                self._initialized = True
                self.set_holdings(self.shy, 1.0)
            return

        price = self._prices[-1]
        sma = sum(self._prices) / SMA_WINDOW
        vol = self._realized_vol()

        if vol is not None:
            self._vol_history.append(vol)

        if len(self._vol_history) < 2:
            median_vol = vol if vol else 0
        else:
            sorted_vols = sorted(self._vol_history)
            mid = len(sorted_vols) // 2
            median_vol = sorted_vols[mid]

        if price > sma:
            if vol is not None and vol < median_vol:
                self.set_holdings(self.dia, 1.0)
                if self.portfolio[self.shy].invested:
                    self.liquidate(self.shy)
            else:
                self.set_holdings(self.dia, 0.5)
                self.set_holdings(self.shy, 0.5)
        else:
            self.set_holdings(self.shy, 1.0)
            if self.portfolio[self.dia].invested:
                self.liquidate(self.dia)
