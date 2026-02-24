"""
Strategy 19: MACD Signal – QQQ vs BND
Period: 2012-01-01 to 2025-12-31
Cadence: Daily
Logic: Compute MACD (12-day EMA - 26-day EMA) and 9-day signal line on QQQ.
       MACD > signal → bullish → QQQ 100%
       MACD <= signal → bearish → BND 100%
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize

START_DATE = "2012-01-01"
END_DATE = "2025-12-31"


class MACDSignalQQQ_Daily(Strategy):
    def __init__(self):
        self._ema12: float | None = None
        self._ema26: float | None = None
        self._signal: float | None = None
        self._count = 0
        self._mult12 = 2.0 / (12 + 1)
        self._mult26 = 2.0 / (26 + 1)
        self._mult9 = 2.0 / (9 + 1)

    def universe(self) -> list[str]:
        return ["QQQ", "BND"]

    def cadence(self) -> Cadence:
        return Cadence(bar_size=BarSize.DAILY)

    def on_data(self, data: Slice, portfolio: PortfolioView) -> dict[str, float] | None:
        price = data.close("QQQ")
        if price is None:
            return None

        self._count += 1

        # Initialize EMAs
        if self._ema12 is None:
            self._ema12 = price
            self._ema26 = price
            return {"BND": 1.0}

        # Update EMAs
        self._ema12 = price * self._mult12 + self._ema12 * (1 - self._mult12)
        self._ema26 = price * self._mult26 + self._ema26 * (1 - self._mult26)

        macd_line = self._ema12 - self._ema26

        # Need at least 26 bars before MACD is meaningful
        if self._count < 26:
            return None

        # Initialize signal line
        if self._signal is None:
            self._signal = macd_line
            return None

        self._signal = macd_line * self._mult9 + self._signal * (1 - self._mult9)

        if self._count < 35:  # 26 + 9 for signal to warm up
            return None

        if macd_line > self._signal:
            return {"QQQ": 1.0}
        else:
            return {"BND": 1.0}
