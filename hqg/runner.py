"""Simple runner for backtesting algorithms.

Users just need to define their algorithm and call run() - everything else is handled.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Type, Optional

from .api.algorithm import Algorithm
from .engine.backtester import Backtester
from .analysis.metrics import PerformanceMetrics


def run(
    algorithm_class: Type[Algorithm],
    universe: List[str],
    start_date: datetime,
    end_date: datetime,
    initial_cash: float = 100_000.0,
    benchmark: Optional[str] = None,
    data_path: str = "db",
    commission_rate: float = 0.005,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Run a backtest with minimal setup.
    
    This is the main entry point for users. Just pass your algorithm class
    and universe, and it handles everything else.
    
    Args:
        algorithm_class: Your algorithm class (subclass of Algorithm)
        universe: List of symbols to trade
        start_date: Start date for backtest
        end_date: End date for backtest
        initial_cash: Starting cash (default: $100,000)
        benchmark: Optional benchmark symbol for comparison
        data_path: Path where data is stored
        commission_rate: Commission per share
        verbose: Whether to print results
        
    Returns:
        Dictionary with backtest results and performance metrics
        
    Example:
        from hqg import run
        from hqg.api import Algorithm
        
        class MyStrategy(Algorithm):
            def Initialize(self):
                self.SetCash(100_000)
            def OnData(self, data):
                # Your logic here
                pass
        
        results = run(
            algorithm_class=MyStrategy,
            universe=["AAPL", "MSFT", "GOOGL"],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31)
        )
    """
    # Setup logging
    if verbose:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        logging.basicConfig(level=logging.WARNING)
    
    logger = logging.getLogger(__name__)
    
    # Log what we're doing
    if verbose:
        logger.info("=" * 80)
        logger.info(f"HQG Backtester - Running Strategy: {algorithm_class.__name__}")
        logger.info("=" * 80)
        logger.info(f"Universe: {', '.join(universe)}")
        logger.info(f"Date Range: {start_date.date()} to {end_date.date()}")
        logger.info(f"Starting Cash: ${initial_cash:,.2f}")
        if benchmark:
            logger.info(f"Benchmark: {benchmark}")
        logger.info("")
    
    # Create backtester
    backtester = Backtester(
        data_path=data_path,
        algorithm_class=algorithm_class,
        initial_cash=initial_cash,
        commission_rate=commission_rate
    )
    
    # Run the backtest
    results = backtester.run_backtest(
        start_date=start_date,
        end_date=end_date,
        symbols=universe
    )
    
    # Format and print results if verbose
    if verbose:
        logger.info("")
        logger.info("=" * 80)
        logger.info("BACKTEST COMPLETE")
        logger.info("=" * 80)
        logger.info("")
        
        metrics = PerformanceMetrics()
        report = metrics.format_metrics_summary(results['performance_report'])
        logger.info(report)
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("Final Portfolio Snapshot")
        logger.info("=" * 80)
        final_snapshot = results['final_snapshot']
        logger.info(f"Cash: ${final_snapshot['cash']:,.2f}")
        logger.info(f"Holdings Value: ${final_snapshot['holdings_value']:,.2f}")
        logger.info(f"Total Equity: ${final_snapshot['total_equity']:,.2f}")
        logger.info("")
        
        if final_snapshot['holdings']:
            logger.info("Open Positions:")
            for symbol, holding in final_snapshot['holdings'].items():
                logger.info(f"  {symbol}: {holding['quantity']} shares @ ${holding['avg_price']:.2f} avg")
                logger.info(f"    Current: ${holding['current_price']:.2f}, P&L: ${holding['unrealized_pnl']:,.2f}")
        
        logger.info("")
        logger.info("Done!")
    
    return results

