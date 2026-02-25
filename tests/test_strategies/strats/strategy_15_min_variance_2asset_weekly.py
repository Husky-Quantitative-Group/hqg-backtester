"""
Strategy 15: Minimum Variance (2-asset simplified) – SPY / TLT
Period: 2006-01-01 to 2021-12-31
Cadence: Weekly
Logic: Compute trailing 26-week covariance matrix for SPY and TLT.
       Solve for the minimum variance portfolio weights (long-only, sum to 1).
       Analytical solution for 2 assets: w_SPY = (σ²_TLT - σ_SPY_TLT) / (σ²_SPY + σ²_TLT - 2·σ_SPY_TLT)
       Clamp to [0, 1].
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize
from collections import deque
import math

START_DATE = "2006-01-01"
END_DATE = "2021-12-31"

LOOKBACK = 26


class MinVariance2Asset_Weekly(Strategy):
    def __init__(self):
        self._spy_prices = deque(maxlen=LOOKBACK + 1)
        self._tlt_prices = deque(maxlen=LOOKBACK + 1)

    def universe(self) -> list[str]:
        return ["SPY", "TLT"]

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.WEEKLY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        spy_p = data.close("SPY")
        tlt_p = data.close("TLT")

        if spy_p is not None:
            self._spy_prices.append(spy_p)
        if tlt_p is not None:
            self._tlt_prices.append(tlt_p)

        if len(self._spy_prices) < LOOKBACK + 1 or len(self._tlt_prices) < LOOKBACK + 1:
            return {"SPY": 0.5, "TLT": 0.5}

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
            return {"SPY": 0.5, "TLT": 0.5}

        w_spy = (var_t - cov_st) / denom
        w_spy = max(0.0, min(1.0, w_spy))  # clamp long-only
        w_tlt = 1.0 - w_spy

        return {"SPY": w_spy, "TLT": w_tlt}
