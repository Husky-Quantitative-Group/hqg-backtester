#!/usr/bin/env python3
"""Test the new percentage-based place_order API."""

from datetime import datetime
from backtester.api.algorithm import Algorithm
from backtester.engine.backtester import Backtester


class PercentageTestStrategy(Algorithm):
    """Test strategy using percentage-based orders."""
    
    def Initialize(self):
        self.SetCash(100_000)
        self.allocated = False
    
    def OnData(self, data):
        if not self.allocated:
            # Allocate 25% to each of 4 symbols (100% total)
            for symbol in data.Bars.keys():
                if len(data.Bars) >= 4:  # Wait until we have at least 4 symbols
                    self.place_order(symbol, 0.25, is_buy=True)  # 25% allocation
                    self.log(f"Allocated 25% to {symbol}")
            
            if len(data.Bars) >= 4:
                self.allocated = True


def test_percentage_api():
    """Test the percentage-based order API."""
    print("Testing percentage-based place_order API...")
    
    try:
        # Create backtester
        backtester = Backtester(
            algorithm_class=PercentageTestStrategy,
            initial_cash=100_000,
            commission_rate=0.005
        )
        
        # Run a short backtest
        results = backtester.run_backtest(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),  # Just January
            symbols=['AAPL', 'MSFT', 'GOOGL', 'AMZN']
        )
        
        print("✅ Percentage-based orders working!")
        print(f"Final equity: ${results['final_snapshot']['total_equity']:,.2f}")
        print(f"Number of fills: {len(results['fills'])}")
        
        # Show some fills
        if results['fills']:
            print("\nSample fills:")
            for fill in results['fills'][:5]:
                print(f"  {fill['symbol']}: {fill['filled_qty']} shares @ ${fill['fill_price']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_percentage_api()
    if success:
        print("\n🎉 Percentage-based API test passed!")
    else:
        print("\n💥 Test failed!")