"""Main backtester orchestrator that coordinates all components."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ..api import Algorithm
from ..analysis.metrics import PerformanceMetrics
from ..data.loader import DataLoader
from ..data.storage import LocalStorage
from ..execution.broker import IBBroker


class Backtester:
    """Main backtester orchestrator that coordinates all components."""

    def __init__(self, 
                 data_path: str | Path,
                 algorithm_class: Type[Algorithm],
                 initial_cash: float = 100_000.0,
                 commission_rate: float = 0.005,
                 log_level: str = "INFO"):
        """Initialize the backtester.
        
        Args:
            data_path: Path to data storage directory
            algorithm_class: Algorithm class to instantiate and run
            initial_cash: Starting capital
            commission_rate: Commission rate per share (default: $0.005)
            log_level: Logging level
        """
        self.data_path = Path(data_path)
        self.algorithm_class = algorithm_class
        self.initial_cash = initial_cash
        self.commission_rate = commission_rate
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.storage = LocalStorage(self.data_path)
        self.data_loader = DataLoader(self.storage)
        self.broker = IBBroker(commission_rate=commission_rate)
        self.performance_metrics = PerformanceMetrics()
        
        # Runtime state
        self.algorithm: Optional[Algorithm] = None
        self.current_time: Optional[datetime] = None
        self.equity_curve: List[Dict[str, Any]] = []
        
        self.logger.info(f"Backtester initialized with ${initial_cash:,.2f} starting capital")

    def run_backtest(self, 
                    start_date: datetime,
                    end_date: datetime,
                    symbols: List[str],
                    algorithm_kwargs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the backtest.
        
        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            symbols: List of symbols to trade
            algorithm_kwargs: Additional arguments for algorithm initialization
            
        Returns:
            Dictionary containing backtest results
        """
        self.logger.info(f"Starting backtest from {start_date} to {end_date}")
        
        # Initialize algorithm
        self.algorithm = self.algorithm_class(**(algorithm_kwargs or {}))
        self.algorithm._set_broker(self.broker)
        self.algorithm._set_data_loader(self.data_loader)
        
        # Set broker starting cash
        self.broker.set_starting_cash(self.initial_cash)
        
        # Load data for all symbols
        self.logger.info(f"Loading data for symbols: {symbols}")
        data_cache = {}
        for symbol in symbols:
            data = self.data_loader.load_data(symbol, start_date, end_date)
            if data is not None and not data.empty:
                data_cache[symbol] = data
                self.logger.info(f"Loaded {len(data)} data points for {symbol}")
            else:
                self.logger.warning(f"No data available for {symbol}")
        
        if not data_cache:
            raise ValueError("No data available for any symbols")
        
        # Initialize algorithm with symbols
        self.algorithm._set_symbols(symbols)
        
        # Call algorithm's Initialize method
        self.logger.info("Initializing algorithm")
        self.algorithm.Initialize()
        
        # Get all unique timestamps across all symbols
        all_timestamps = set()
        for symbol_data in data_cache.values():
            all_timestamps.update(symbol_data.index)
        
        sorted_timestamps = sorted(all_timestamps)
        self.logger.info(f"Processing {len(sorted_timestamps)} time steps")
        
        # Main event loop
        for timestamp in sorted_timestamps:
            self.current_time = timestamp
            
            # Create data slice for current timestamp
            slice_data = {}
            for symbol, symbol_data in data_cache.items():
                if timestamp in symbol_data.index:
                    slice_data[symbol] = symbol_data.loc[timestamp]
            
            if not slice_data:
                continue
            
            # Create Slice object
            from ..api import Slice, TradeBar
            trade_bars = {}
            for symbol, data in slice_data.items():
                trade_bars[symbol] = TradeBar(
                    symbol=symbol,
                    open=float(data['open']),
                    high=float(data['high']),
                    low=float(data['low']),
                    close=float(data['close']),
                    volume=int(data['volume']),
                    end_time=timestamp
                )
            
            slice_obj = Slice(trade_bars)
            
            # Set current time in algorithm
            self.algorithm._set_current_time(timestamp)
            
            # Call algorithm's OnData method
            try:
                self.algorithm.OnData(slice_obj)
            except Exception as e:
                self.logger.error(f"Error in algorithm OnData at {timestamp}: {e}")
                continue
            
            # Settle orders for each symbol
            for symbol in slice_data.keys():
                close_price = float(slice_data[symbol]['close'])
                filled_orders = self.broker.settle(symbol, close_price, timestamp)
                
                # Log fills
                for fill in filled_orders:
                    self.logger.debug(
                        f"Fill: {fill['symbol']} {fill['filled_qty']} @ "
                        f"${fill['fill_price']:.2f} (${fill['commission']:.2f} commission)"
                    )
            
            # Record equity curve
            snapshot = self.broker.snapshot()
            self.equity_curve.append({
                'time': timestamp,
                'equity': snapshot['total_equity'],
                'cash': snapshot['cash'],
                'holdings_value': snapshot['holdings_value'],
            })
        
        # Generate performance report
        self.logger.info("Generating performance report")
        fills = self.broker.get_fills()
        final_snapshot = self.broker.snapshot()
        performance_report = self.performance_metrics.generate_performance_report(
            equity_curve=self.equity_curve,
            fills=fills,
            initial_cash=self.initial_cash
        )
        
        # Add open positions info to report
        performance_report['open_positions'] = final_snapshot.get('holdings', {})
        performance_report['total_fills'] = len(fills)
        
        # Log summary
        summary = self.performance_metrics.format_metrics_summary(performance_report)
        self.logger.info(f"\n{summary}")
        
        # Prepare results
        results = {
            'equity_curve': self.equity_curve,
            'fills': fills,
            'orders': self.broker.get_orders(),
            'performance_report': performance_report,
            'final_snapshot': self.broker.snapshot(),
            'start_date': start_date,
            'end_date': end_date,
            'symbols': symbols,
            'initial_cash': self.initial_cash,
        }
        
        self.logger.info(f"Backtest completed. Final equity: ${results['final_snapshot']['total_equity']:,.2f}")
        
        return results

    def save_results(self, results: Dict[str, Any], output_path: str | Path) -> None:
        """Save backtest results to file.
        
        Args:
            results: Backtest results dictionary
            output_path: Path to save results
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        import json
        
        # Convert datetime objects to strings for JSON serialization
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj
        
        # Save results as JSON
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=convert_datetime)
        
        self.logger.info(f"Results saved to {output_path}")

    def plot_results(self, results: Dict[str, Any], save_path: Optional[str | Path] = None) -> None:
        """Plot backtest results.

        this is chatt'd
        
        Args:
            results: Backtest results dictionary
            save_path: Optional path to save plot
        """
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            # Set style
            plt.style.use('seaborn-v0_8')
            sns.set_palette("husl")
            
            # Create figure with subplots
            fig, axes = plt.subplots(3, 2, figsize=(15, 12))
            fig.suptitle('Backtest Performance Analysis', fontsize=16, fontweight='bold')
            
            # Plot 1: Equity Curve
            equity_df = pd.DataFrame(results['equity_curve'])
            equity_df['time'] = pd.to_datetime(equity_df['time'])
            equity_df = equity_df.set_index('time')
            
            axes[0, 0].plot(equity_df.index, equity_df['equity'], label='Portfolio Equity', linewidth=2)
            axes[0, 0].axhline(y=results['initial_cash'], color='red', linestyle='--', alpha=0.7, label='Initial Capital')
            axes[0, 0].set_title('Equity Curve')
            axes[0, 0].set_xlabel('Date')
            axes[0, 0].set_ylabel('Equity ($)')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)
            
            # Plot 2: Drawdown
            returns = equity_df['equity'].pct_change().dropna()
            cumulative_returns = (1 + returns).cumprod()
            running_max = cumulative_returns.cummax()
            drawdown = (cumulative_returns - running_max) / running_max
            
            axes[0, 1].fill_between(drawdown.index, drawdown * 100, 0, alpha=0.3, color='red')
            axes[0, 1].plot(drawdown.index, drawdown * 100, color='red', linewidth=1)
            axes[0, 1].set_title('Drawdown')
            axes[0, 1].set_xlabel('Date')
            axes[0, 1].set_ylabel('Drawdown (%)')
            axes[0, 1].grid(True, alpha=0.3)
            
            # Plot 3: Daily Returns Distribution
            axes[1, 0].hist(returns * 100, bins=50, alpha=0.7, edgecolor='black')
            axes[1, 0].axvline(x=returns.mean() * 100, color='red', linestyle='--', label=f'Mean: {returns.mean()*100:.2f}%')
            axes[1, 0].set_title('Daily Returns Distribution')
            axes[1, 0].set_xlabel('Daily Return (%)')
            axes[1, 0].set_ylabel('Frequency')
            axes[1, 0].legend()
            axes[1, 0].grid(True, alpha=0.3)
            
            # Plot 4: Rolling Metrics
            window = 30
            rolling_sharpe = (returns.rolling(window=window).mean() / returns.rolling(window=std())) * np.sqrt(252)
            
            axes[1, 1].plot(rolling_sharpe.index, rolling_sharpe, label=f'{window}-day Rolling Sharpe', linewidth=2)
            axes[1, 1].axhline(y=0, color='black', linestyle='-', alpha=0.3)
            axes[1, 1].set_title('Rolling Sharpe Ratio')
            axes[1, 1].set_xlabel('Date')
            axes[1, 1].set_ylabel('Sharpe Ratio')
            axes[1, 1].legend()
            axes[1, 1].grid(True, alpha=0.3)
            
            # Plot 5: Trade P&L Distribution
            if results['fills']:
                fills_df = pd.DataFrame(results['fills'])
                # Calculate trade P&L (simplified)
                trade_pnl = []
                for i, fill in enumerate(fills_df.itertuples()):
                    if fill.direction == 'sell':
                        # Find matching buy (simplified)
                        buy_fills = fills_df[(fills_df['symbol'] == fill.symbol) & 
                                           (fills_df['direction'] == 'buy') & 
                                           (fills_df.index < i)]
                        if not buy_fills.empty:
                            buy_price = buy_fills.iloc[-1]['fill_price']
                            pnl = (fill.fill_price - buy_price) * fill.filled_qty - fill.commission
                            trade_pnl.append(pnl)
                
                if trade_pnl:
                    axes[2, 0].hist(trade_pnl, bins=30, alpha=0.7, edgecolor='black')
                    axes[2, 0].axvline(x=np.mean(trade_pnl), color='red', linestyle='--', 
                                     label=f'Avg P&L: ${np.mean(trade_pnl):.2f}')
                    axes[2, 0].set_title('Trade P&L Distribution')
                    axes[2, 0].set_xlabel('Trade P&L ($)')
                    axes[2, 0].set_ylabel('Frequency')
                    axes[2, 0].legend()
                    axes[2, 0].grid(True, alpha=0.3)
            
            # Plot 6: Monthly Returns Heatmap
            monthly_returns = returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
            monthly_returns_df = monthly_returns.to_frame('returns')
            monthly_returns_df['year'] = monthly_returns_df.index.year
            monthly_returns_df['month'] = monthly_returns_df.index.month
            
            pivot_table = monthly_returns_df.pivot(index='year', columns='month', values='returns')
            
            if not pivot_table.empty:
                sns.heatmap(pivot_table * 100, annot=True, fmt='.1f', cmap='RdYlGn', 
                           center=0, ax=axes[2, 1], cbar_kws={'label': 'Return (%)'})
                axes[2, 1].set_title('Monthly Returns Heatmap')
                axes[2, 1].set_xlabel('Month')
                axes[2, 1].set_ylabel('Year')
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                self.logger.info(f"Plot saved to {save_path}")
            
            plt.show()
            
        except ImportError:
            self.logger.warning("Matplotlib and/or seaborn not available. Skipping plots.")
        except Exception as e:
            self.logger.error(f"Error creating plots: {e}")

    def get_algorithm_logs(self) -> List[str]:
        """Get logs from the algorithm."""
        if self.algorithm:
            return self.algorithm.get_logs()
        return []

    def validate_setup(self) -> bool:
        """Validate that the backtester setup is correct.
        
        Returns:
            True if setup is valid, False otherwise
        """
        try:
            # Check data path
            if not self.data_path.exists():
                self.logger.error(f"Data path does not exist: {self.data_path}")
                return False
            
            # Check algorithm class
            if not issubclass(self.algorithm_class, Algorithm):
                self.logger.error("Algorithm class must inherit from Algorithm")
                return False
            
            # Check initial cash
            if self.initial_cash <= 0:
                self.logger.error("Initial cash must be positive")
                return False
            
            # Check commission rate
            if self.commission_rate < 0:
                self.logger.error("Commission rate must be non-negative")
                return False
            
            self.logger.info("Setup validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Setup validation failed: {e}")
            return False
