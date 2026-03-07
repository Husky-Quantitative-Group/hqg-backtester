from hqg_algorithms import Strategy, Cadence, BarSize, Slice, PortfolioView, Signal, TargetWeights, Hold

class MyStrategy(Strategy):
    universe = ["SPY", "TLT"]
    cadence = Cadence(bar_size=BarSize.DAILY)

    def __init__(self):
        self.isInvested = False

    def on_data(self, data: Slice, portfolio: PortfolioView) -> Signal:
        if not self.isInvested:
            self.isInvested = True
            return TargetWeights({"SPY": 0.6, "TLT": 0.4})
        return Hold()
