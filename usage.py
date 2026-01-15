from hqg_algorithms import Strategy, Cadence, Slice, PortfolioView
from src.services.backtester import Backtester
from datetime import datetime
import asyncio

# example usage
class MyStrategy(Strategy):
    def __init__(self):
        self.isInvested = False

    def universe(self):
        return ["SPY", "TLT"]
    
    def cadence(self):
        return Cadence()
    
    def on_data(self, data: Slice, portfolio: PortfolioView):
        if not self.isInvested:
            self.isInvested = True
            return {"SPY": 0.6, "TLT": 0.4}
        return None

async def main():
    bt = Backtester()

    result = await bt.run(
        strategy=MyStrategy(),
        start_date=datetime(2022, 1, 1),
        end_date=datetime(2024, 12, 31),
        initial_capital=10000
    )

    print(f"Final value: ${result.final_value:.2f}")
    print(f"Total return: {result.metrics.total_return:.2%}")
    print(f"Sharpe ratio: {result.metrics.sharpe_ratio:.2f}")

if __name__ == "__main__":
    asyncio.run(main())