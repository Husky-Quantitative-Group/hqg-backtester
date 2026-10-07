"""
Strategy 21: GDP Growth Regime - SPY vs TLT
Period: 2000-01-01 to 2026-01-01
Cadence: Daily
Logic: Compute year-over-year real GDP growth from FRED.GDP.
       Hold SPY when YoY GDP growth is above 2% and accelerating.
       Otherwise hold TLT as the defensive asset.
No shorting.
"""
from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView, BarSize, Signal, TargetWeights, Hold

START_DATE = "2000-01-01"
END_DATE = "2026-01-01"


class GDPGrowthRegimeQuarterly(Strategy):
    universe = ["SPY", "TLT"]
    alt_data = ["FRED.GDP"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def __init__(self):
        self._growth_threshold = 0.02
        self._last_target: str | None = None

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        if data.close("SPY") is None or data.close("TLT") is None:
            return Hold()

        gdp_history = sorted(data.alt_series("FRED.GDP").items())

        # Need six quarterly observations to compute two YoY growth readings:
        # latest vs four quarters ago, and previous vs five quarters ago.
        if len(gdp_history) < 6:
            return TargetWeights({"TLT": 1.0})

        latest_gdp = gdp_history[-1][1]
        year_ago_gdp = gdp_history[-5][1]
        previous_gdp = gdp_history[-2][1]
        previous_year_ago_gdp = gdp_history[-6][1]

        if year_ago_gdp <= 0 or previous_year_ago_gdp <= 0:
            return TargetWeights({"TLT": 1.0})

        latest_yoy_growth = (latest_gdp / year_ago_gdp) - 1.0
        previous_yoy_growth = (previous_gdp / previous_year_ago_gdp) - 1.0

        target = (
            "SPY"
            if latest_yoy_growth > self._growth_threshold and latest_yoy_growth > previous_yoy_growth
            else "TLT"
        )

        if target == self._last_target:
            return Hold()

        self._last_target = target
        return TargetWeights({target: 1.0})
