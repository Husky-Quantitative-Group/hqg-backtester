"""
QC Strategy 09: Inverse Volatility Weighting – SPY, TLT, GLD
Period: 2007-01-01 to 2022-12-31
Cadence: Weekly
Logic: Compute trailing 12-week realized volatility for each asset.
       Allocate inversely proportional to volatility (risk parity lite).
No shorting. No fees.
"""
from AlgorithmImports import *
from collections import deque
import math


TICKERS = ["SPY", "TLT", "GLD"]
VOL_WINDOW = 12


class InverseVolWeekly(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2007, 1, 1)
        self.set_end_date(2022, 12, 31)
        self.set_cash(10000)

        self.set_security_initializer(
            lambda s: s.set_fee_model(ConstantFeeModel(0, "USD"))
        )

        self._symbols = {}
        for t in TICKERS:
            self._symbols[t] = self.add_equity(t, Resolution.DAILY).symbol

        self._prices = {t: deque(maxlen=VOL_WINDOW + 1) for t in TICKERS}

        self.schedule.on(
            self.date_rules.week_start("SPY"),
            self.time_rules.after_market_open("SPY", 30),
            self._rebalance,
        )

    def on_data(self, data):
        for t in TICKERS:
            sym = self._symbols[t]
            if data.bars.contains_key(sym):
                self._prices[t].append(data.bars[sym].close)

    def _realized_vol(self, ticker):
        prices = list(self._prices[ticker])
        if len(prices) < VOL_WINDOW + 1:
            return None
        returns = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
        mean_ret = sum(returns) / len(returns)
        var = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        return math.sqrt(var) if var > 0 else None

    def _rebalance(self):
        vols = {}
        for t in TICKERS:
            v = self._realized_vol(t)
            if v is not None and v > 1e-10:
                vols[t] = v

        if not vols:
            # Equal weight fallback
            available = [t for t in TICKERS if self.securities[self._symbols[t]].price > 0]
            if not available:
                return
            w = 1.0 / len(available)
            for t in TICKERS:
                if t in available:
                    self.set_holdings(self._symbols[t], w)
                elif self.portfolio[self._symbols[t]].invested:
                    self.liquidate(self._symbols[t])
            return

        inv_vols = {t: 1.0 / v for t, v in vols.items()}
        total = sum(inv_vols.values())
        weights = {t: iv / total for t, iv in inv_vols.items()}

        for t in TICKERS:
            if t in weights:
                self.set_holdings(self._symbols[t], weights[t])
            elif self.portfolio[self._symbols[t]].invested:
                self.liquidate(self._symbols[t])
