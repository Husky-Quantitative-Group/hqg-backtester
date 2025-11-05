#!/usr/bin/env python3

from datetime import datetime
from backtester.api.algorithm import Algorithm
from backtester.engine.backtester import Backtester

class BuyAndHoldStrategy(Algorithm):
    """Simple buy and hold strategy - invest entire portfolio on first day."""
    
    def Initialize(self):
        self.SetCash(100_000)
        self.invested = False
    
    def OnData(self, data):
        if not self.invested and data.Bars:
            # Check actual cash available
            cash_available = self._broker._cash
            self.log(f"Cash available: ${cash_available:,.2f}")
            
            # Invest entire portfolio in SPY
            self.place_order("SPY", 1.0, is_buy=True)  # 100% allocation
            self.log(f"Invested 100% in SPY")
            self.invested = True

if __name__ == "__main__":
    print("SPY Buy & Hold Strategy Test")
    print("=" * 40)
    print("Period: 2023-01-01 to 2025-01-01")
    print("Fees: Disabled")
    print("Strategy: 100% SPY buy and hold")
    print()
    
    # Create backtester with zero fees
    backtester = Backtester(
        algorithm_class=BuyAndHoldStrategy,
        initial_cash=100_000,
        commission_rate=0.0  # Zero fees
    )
    
    # Run backtest
    results = backtester.run_backtest(
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2025, 1, 1),
        symbols=["SPY"]
    )
    
    # Calculate performance metrics
    initial_cash = 100_000
    final_equity = results['final_snapshot']['total_equity']
    total_return = (final_equity - initial_cash) / initial_cash
    
    # Calculate CAGR (2 years exactly)
    years = 2.0
    cagr = (final_equity / initial_cash) ** (1/years) - 1
    
    print("RESULTS:")
    print(f"Initial cash: ${initial_cash:,.2f}")
    print(f"Final equity: ${final_equity:,.2f}")
    print(f"Total return: {total_return:.2%}")
    print(f"CAGR: {cagr:.2%}")
    
    # Show trade details
    if results['fills']:
        print(f"\nTRADE DETAILS:")
        fill = results['fills'][0]
        shares = fill['filled_qty']
        price = fill['fill_price']
        commission = fill['commission']
        print(f"Shares purchased: {shares:,.0f}")
        print(f"Purchase price: ${price:.2f}")
        print(f"Total invested: ${shares * price:,.2f}")
        print(f"Commission paid: ${commission:.2f}")
        
        # Calculate implied final SPY price
        final_spy_price = final_equity / shares
        print(f"Implied final SPY price: ${final_spy_price:.2f}")
    
    # Performance metrics from backtester
    if 'performance_metrics' in results:
        metrics = results['performance_metrics']
        print(f"\nPERFORMANCE METRICS:")
        for key, value in metrics.items():
            if isinstance(value, float):
                if 'return' in key or 'ratio' in key:
                    print(f"{key.replace('_', ' ').title()}: {value:.2%}")
                else:
                    print(f"{key.replace('_', ' ').title()}: {value:.2f}")
            else:
                print(f"{key.replace('_', ' ').title()}: {value}")
    
    print(f"\nCOMPARISON:")
    print(f"Expected SPY CAGR (382→595): {((595/382)**(1/2) - 1):.2%}")
    print(f"Your backtester CAGR: {cagr:.2%}")
    print(f"QuantConnect CAGR: 25.14%")
    
    print(f"\n✅ Buy and hold test completed!")