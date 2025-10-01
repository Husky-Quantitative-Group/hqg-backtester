"""Performance metrics and analytics for backtesting results."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats


class PerformanceMetrics:
    """Calculate and analyze performance metrics for backtesting results."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def calculate_returns(self, equity_curve: List[Dict[str, Any]]) -> pd.Series:
        """Calculate daily returns from equity curve."""
        if not equity_curve:
            return pd.Series(dtype=float)
        
        # Convert to DataFrame
        df = pd.DataFrame(equity_curve)
        df['time'] = pd.to_datetime(df['time'])
        df = df.set_index('time')
        
        # Calculate returns based on actual data points (no resampling)
        returns = df['equity'].pct_change().dropna()
        
        return returns

    def calculate_basic_metrics(self, equity_curve: List[Dict[str, Any]], 
                             initial_cash: float = 100_000.0) -> Dict[str, float]:
        """Calculate basic performance metrics."""
        if not equity_curve:
            return {}
        
        returns = self.calculate_returns(equity_curve)
        
        if returns.empty:
            # Handle single equity point case
            if len(equity_curve) == 1:
                if initial_cash == 0:
                    total_return = 0.0
                else:
                    total_return = (equity_curve[0]['equity'] / initial_cash) - 1
                return {
                    "total_return": total_return,
                    "annualized_return": 0.0,
                    "volatility": 0.0,
                    "sharpe_ratio": 0.0,
                    "sortino_ratio": 0.0,
                    "max_drawdown": 0.0,
                    "calmar_ratio": 0.0
                }
            return {}
        
        # Total return
        total_return = (equity_curve[-1]['equity'] / initial_cash) - 1
        
        # Annualized return
        days = (pd.to_datetime(equity_curve[-1]['time']) - 
                pd.to_datetime(equity_curve[0]['time'])).days
        years = max(days / 365.25, 1/365.25)  # Avoid division by zero
        annualized_return = (1 + total_return) ** (1/years) - 1
        
        # Volatility (annualized)
        daily_vol = returns.std()
        annualized_vol = daily_vol * np.sqrt(252)
        
        # Sharpe ratio (assuming risk-free rate of 0)
        sharpe_ratio = annualized_return / annualized_vol if annualized_vol > 0 else 0
        
        # Sortino ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_vol = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino_ratio = annualized_return / downside_vol if downside_vol > 0 else 0
        
        # Max drawdown
        cumulative_returns = (1 + returns).cumprod()
        running_max = cumulative_returns.cummax()
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Calmar ratio
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Win rate
        win_rate = (returns > 0).mean()
        
        # Profit factor
        positive_returns = returns[returns > 0]
        negative_returns = returns[returns < 0]
        profit_factor = (positive_returns.sum() / abs(negative_returns.sum())) if len(negative_returns) > 0 else float('inf')
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'annualized_volatility': annualized_vol,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown': max_drawdown,
            'calmar_ratio': calmar_ratio,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_days': days,
        }

    def calculate_trade_metrics(self, fills: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate trade-specific metrics."""
        if not fills:
            return {}
        
        # Group fills by symbol and calculate P&L for each trade
        trades = []
        symbol_positions = {}
        
        for fill in fills:
            symbol = fill['symbol']
            direction = fill['direction']
            quantity = fill['filled_qty']
            price = fill['fill_price']
            commission = fill['commission']
            
            if symbol not in symbol_positions:
                symbol_positions[symbol] = []
            
            if direction == 'buy':
                symbol_positions[symbol].append({
                    'quantity': quantity,
                    'price': price,
                    'commission': commission,
                    'timestamp': fill['time']
                })
            else:  # sell
                # Match with previous buys (FIFO)
                remaining_sell = quantity
                total_cost = 0
                total_commission = commission
                
                while remaining_sell > 0 and symbol_positions[symbol]:
                    buy = symbol_positions[symbol][0]
                    trade_qty = min(remaining_sell, buy['quantity'])
                    
                    # Calculate P&L for this trade
                    trade_revenue = trade_qty * price
                    trade_cost = trade_qty * buy['price']
                    trade_pnl = trade_revenue - trade_cost - buy['commission'] * (trade_qty / buy['quantity'])
                    
                    trades.append({
                        'symbol': symbol,
                        'quantity': trade_qty,
                        'entry_price': buy['price'],
                        'exit_price': price,
                        'pnl': trade_pnl,
                        'return': (price - buy['price']) / buy['price'],
                        'duration': (fill['time'] - buy['timestamp']).days,
                        'commission': total_commission,
                    })
                    
                    remaining_sell -= trade_qty
                    buy['quantity'] -= trade_qty
                    
                    if buy['quantity'] == 0:
                        symbol_positions[symbol].pop(0)
        
        if not trades:
            return {}
        
        trades_df = pd.DataFrame(trades)
        
        # Calculate trade metrics
        total_trades = len(trades)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        
        avg_trade_duration = trades_df['duration'].mean()
        
        largest_win = trades_df['pnl'].max()
        largest_loss = trades_df['pnl'].min()
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'trade_win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'avg_trade_duration_days': avg_trade_duration,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
        }

    def calculate_risk_metrics(self, returns: pd.Series, benchmark_returns: Optional[pd.Series] = None) -> Dict[str, float]:
        """Calculate risk metrics including beta and alpha."""
        if returns.empty:
            return {}
        
        metrics = {}
        
        # Value at Risk (VaR) at 95% confidence level
        var_95 = returns.quantile(0.05)
        metrics['var_95'] = var_95
        
        # Expected Shortfall (CVaR) at 95% confidence level
        cvar_95 = returns[returns <= var_95].mean()
        metrics['cvar_95'] = cvar_95
        
        # Skewness and Kurtosis
        metrics['skewness'] = returns.skew()
        metrics['kurtosis'] = returns.kurtosis()
        
        # Beta and Alpha (if benchmark provided)
        if benchmark_returns is not None and len(benchmark_returns) > 0:
            # Align dates
            aligned_returns = returns.align(benchmark_returns, join='inner')
            strategy_returns = aligned_returns[0]
            bench_returns = aligned_returns[1]
            
            if len(strategy_returns) > 1:
                # Calculate beta
                covariance = np.cov(strategy_returns, bench_returns)[0, 1]
                bench_variance = np.var(bench_returns)
                beta = covariance / bench_variance if bench_variance > 0 else 0
                metrics['beta'] = beta
                
                # Calculate alpha (annualized)
                alpha = (strategy_returns.mean() - beta * bench_returns.mean()) * 252
                metrics['alpha'] = alpha
                
                # Information ratio
                tracking_error = (strategy_returns - bench_returns).std() * np.sqrt(252)
                excess_return = (strategy_returns.mean() - bench_returns.mean()) * 252
                information_ratio = excess_return / tracking_error if tracking_error > 0 else 0
                metrics['information_ratio'] = information_ratio
        
        return metrics

    def generate_performance_report(self, equity_curve: List[Dict[str, Any]], 
                                 fills: List[Dict[str, Any]], 
                                 initial_cash: float = 100_000.0,
                                 benchmark_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        report = {
            'summary': {},
            'returns_metrics': {},
            'trade_metrics': {},
            'risk_metrics': {},
            'benchmark_comparison': {},
        }
        
        # Basic metrics
        basic_metrics = self.calculate_basic_metrics(equity_curve, initial_cash)
        report['summary'] = basic_metrics
        
        # Returns analysis
        returns = self.calculate_returns(equity_curve)
        if not returns.empty:
            report['returns_metrics'] = {
                'daily_returns_mean': returns.mean(),
                'daily_returns_std': returns.std(),
                'best_day': returns.max(),
                'worst_day': returns.min(),
                'positive_days': (returns > 0).sum(),
                'negative_days': (returns < 0).sum(),
            }
        
        # Trade metrics
        trade_metrics = self.calculate_trade_metrics(fills)
        report['trade_metrics'] = trade_metrics
        
        # Risk metrics
        if not returns.empty:
            risk_metrics = self.calculate_risk_metrics(returns)
            report['risk_metrics'] = risk_metrics
        
        # Benchmark comparison
        if benchmark_data is not None and not returns.empty:
            benchmark_returns = benchmark_data['close'].pct_change().dropna()
            benchmark_returns.index = pd.to_datetime(benchmark_returns.index)
            
            # Align dates
            aligned_returns = returns.align(benchmark_returns, join='inner')
            if len(aligned_returns[0]) > 0:
                strategy_returns = aligned_returns[0]
                bench_returns = aligned_returns[1]
                
                # Calculate relative performance
                strategy_cum_return = (1 + strategy_returns).cumprod().iloc[-1] - 1
                bench_cum_return = (1 + bench_returns).cumprod().iloc[-1] - 1
                
                # Calculate correlation safely
                try:
                    # Check if we have enough data points and there's variance in the data
                    if len(strategy_returns) > 1 and strategy_returns.std() > 0 and bench_returns.std() > 0:
                        correlation = strategy_returns.corr(bench_returns)
                    else:
                        correlation = float('nan')  # Not enough data or no variance
                except Exception:
                    correlation = float('nan')
                
                # Calculate benchmark Sharpe ratio
                bench_annualized_return = bench_returns.mean() * 252
                bench_annualized_vol = bench_returns.std() * np.sqrt(252)
                bench_sharpe = bench_annualized_return / bench_annualized_vol if bench_annualized_vol > 0 else 0
                
                # Calculate benchmark max drawdown
                bench_cumulative = (1 + bench_returns).cumprod()
                bench_running_max = bench_cumulative.cummax()
                bench_drawdown = (bench_cumulative - bench_running_max) / bench_running_max
                bench_max_drawdown = bench_drawdown.min()
                
                # Calculate beta and alpha
                covariance = np.cov(strategy_returns, bench_returns)[0, 1]
                bench_variance = np.var(bench_returns)
                beta = covariance / bench_variance if bench_variance > 0 else 0
                
                # Alpha (annualized) - Jensen's alpha
                strategy_annualized_return = strategy_returns.mean() * 252
                alpha = strategy_annualized_return - (beta * bench_annualized_return)
                
                report['benchmark_comparison'] = {
                    'strategy_cumulative_return': strategy_cum_return,
                    'benchmark_cumulative_return': bench_cum_return,
                    'excess_return': strategy_cum_return - bench_cum_return,
                    'correlation': correlation,
                    'strategy_sharpe': basic_metrics.get('sharpe_ratio', 0),
                    'benchmark_sharpe': bench_sharpe,
                    'strategy_max_drawdown': basic_metrics.get('max_drawdown', 0),
                    'benchmark_max_drawdown': bench_max_drawdown,
                    'beta': beta,
                    'alpha': alpha,
                }
        
        # Add timestamp
        report['generated_at'] = datetime.now().isoformat()
        
        return report

    def format_metrics_summary(self, report: Dict[str, Any]) -> str:
        """Format metrics report into a readable summary."""
        summary = []
        
        # Header
        summary.append("=== PERFORMANCE REPORT ===")
        summary.append(f"Generated: {report.get('generated_at', 'N/A')}")
        summary.append("")
        
        # Summary metrics
        if 'summary' in report:
            smry = report['summary']
            summary.append("=== SUMMARY ===")
            summary.append(f"Total Return: {smry.get('total_return', 0):.2%}")
            summary.append(f"Annualized Return: {smry.get('annualized_return', 0):.2%}")
            summary.append(f"Sharpe Ratio: {smry.get('sharpe_ratio', 0):.2f}")
            summary.append(f"Max Drawdown: {smry.get('max_drawdown', 0):.2%}")
            summary.append(f"Win Rate: {smry.get('win_rate', 0):.2%}")
            summary.append("")
        
        # Trade metrics
        if 'trade_metrics' in report:
            trade = report['trade_metrics']
            summary.append("=== TRADE METRICS (CLOSED TRADES) ===")
            total_trades = trade.get('total_trades', 0)
            if total_trades == 0:
                summary.append("No closed trades (all positions still open)")
                summary.append("Note: Returns shown above include unrealized P&L from open positions")
            else:
                summary.append(f"Total Trades: {total_trades}")
                summary.append(f"Winning Trades: {trade.get('winning_trades', 0)}")
                summary.append(f"Losing Trades: {trade.get('losing_trades', 0)}")
                summary.append(f"Trade Win Rate: {trade.get('trade_win_rate', 0):.2%}")
                summary.append(f"Avg Win: ${trade.get('avg_win', 0):.2f}")
                summary.append(f"Avg Loss: ${trade.get('avg_loss', 0):.2f}")
                summary.append(f"Profit Factor: {trade.get('profit_factor', 0):.2f}")
            summary.append("")
        
        # Risk metrics
        if 'risk_metrics' in report:
            risk = report['risk_metrics']
            summary.append("=== RISK METRICS ===")
            summary.append(f"VaR (95%): {risk.get('var_95', 0):.2%}")
            summary.append(f"CVaR (95%): {risk.get('cvar_95', 0):.2%}")
            summary.append(f"Skewness: {risk.get('skewness', 0):.2f}")
            summary.append(f"Kurtosis: {risk.get('kurtosis', 0):.2f}")
            if 'beta' in risk:
                summary.append(f"Beta: {risk.get('beta', 0):.2f}")
                summary.append(f"Alpha: {risk.get('alpha', 0):.2%}")
            summary.append("")
        
        # Benchmark comparison
        if 'benchmark_comparison' in report:
            bench = report['benchmark_comparison']
            summary.append("=== BENCHMARK COMPARISON ===")
            summary.append(f"Strategy Return: {bench.get('strategy_cumulative_return', 0):.2%}")
            summary.append(f"Benchmark Return: {bench.get('benchmark_cumulative_return', 0):.2%}")
            summary.append(f"Excess Return: {bench.get('excess_return', 0):.2%}")
            summary.append("")
            summary.append(f"Strategy Sharpe Ratio: {bench.get('strategy_sharpe', 0):.2f}")
            summary.append(f"Benchmark Sharpe Ratio: {bench.get('benchmark_sharpe', 0):.2f}")
            summary.append("")
            summary.append(f"Strategy Max Drawdown: {bench.get('strategy_max_drawdown', 0):.2%}")
            summary.append(f"Benchmark Max Drawdown: {bench.get('benchmark_max_drawdown', 0):.2%}")
            summary.append("")
            summary.append(f"Beta (Market Sensitivity): {bench.get('beta', 0):.2f}")
            summary.append(f"Alpha (Excess Return): {bench.get('alpha', 0):.2%}")
            summary.append("")
            summary.append(f"Correlation: {bench.get('correlation', 0):.2f}")
        
        # Open positions (if no closed trades)
        if 'open_positions' in report and report.get('total_fills', 0) > 0:
            if report.get('trade_metrics', {}).get('total_trades', 0) == 0:
                summary.append("")
                summary.append("=== OPEN POSITIONS ===")
                open_pos = report['open_positions']
                if open_pos:
                    for symbol, pos in open_pos.items():
                        pnl_pct = (pos.get('unrealized_pnl', 0) / (pos.get('quantity', 1) * pos.get('avg_price', 1))) * 100
                        summary.append(f"{symbol}: {pos.get('quantity', 0)} shares @ ${pos.get('avg_price', 0):.2f} avg")
                        summary.append(f"  Current: ${pos.get('current_price', 0):.2f}, Unrealized P&L: ${pos.get('unrealized_pnl', 0):,.2f} ({pnl_pct:+.2f}%)")
                else:
                    summary.append("No open positions")
        
        return "\n".join(summary)
