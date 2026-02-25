"""
Strategy 09: Inverse Volatility Weighting – SPY, TLT, GLD
Period: 2007-01-01 to 2022-12-31
Cadence: Weekly
Logic: Compute trailing 12-week realized volatility for each asset.
       Allocate inversely proportional to volatility (risk parity lite).
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize
from collections import deque
import math

START_DATE = "2007-01-01"
END_DATE = "2022-12-31"

TICKERS = ["SPY", "TLT", "GLD"]
VOL_WINDOW = 12


class InverseVolWeekly(Strategy):
    def __init__(self):
        self._prices: dict[str, deque] = {
            t: deque(maxlen=VOL_WINDOW + 1) for t in TICKERS
        }

    def universe(self) -> list[str]:
        return TICKERS

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.WEEKLY)

    def _realized_vol(self, ticker: str) -> float | None:
        prices = list(self._prices[ticker])
        if len(prices) < VOL_WINDOW + 1:
            return None

        returns = [
            math.log(prices[i] / prices[i - 1])
            for i in range(1, len(prices))
        ]
        mean_ret = sum(returns) / len(returns)
        var = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        return math.sqrt(var) if var > 0 else None

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        for t in TICKERS:
            p = data.close(t)
            if p is not None:
                self._prices[t].append(p)

        vols = {}
        for t in TICKERS:
            v = self._realized_vol(t)
            if v is not None and v > 1e-10:
                vols[t] = v

        if not vols:
            # Equal weight fallback
            available = [t for t in TICKERS if data.close(t) is not None]
            if not available:
                return None
            w = 1.0 / len(available)
            return {t: w for t in available}

        # Inverse vol weighting
        inv_vols = {t: 1.0 / v for t, v in vols.items()}
        total = sum(inv_vols.values())
        return {t: iv / total for t, iv in inv_vols.items()}
