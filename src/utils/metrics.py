# src.utils.metrics
import numpy as np
import pandas as pd
import yfinance as yf
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from ..models.portfolio import Portfolio
from ..models.response import Trade, PerformanceMetrics
from math import erf, sqrt

# TODO: make sharpe ratio calc more robust (fr = avg 10 year tbill return across test timeline)
# TODO: add max drawdown recovery
# TODO: ensure daily returns map long term

def calculate_metrics(portfolio: Portfolio, trades: List[Trade], initial_capital: float) -> PerformanceMetrics:

    equity_curve = pd.Series(portfolio.equity_curve)
    returns = equity_curve.pct_change().dropna()
    
    # total return
    final_value = equity_curve.iloc[-1] if len(equity_curve) > 0 else initial_capital
    total_return = (final_value - initial_capital) / initial_capital
    
    # annualized return
    if len(equity_curve) > 1:
        # arith calc: (closer to ground truth in short term test)
        annualized_return = returns.mean() * 252
        # geometric calc:
        # annualized_return = (1 + returns).prod() ** (252 / len(returns)) - 1      

    else:
        annualized_return = 0.0
        
    sharpe_ratio = _calculate_sharpe(returns)
    sortino_ratio = _calculate_sortino(returns)
    max_drawdown = _calculate_max_drawdown(equity_curve)
    win_rate = _calculate_win_rate(trades)
    avg_win, avg_loss = _calculate_avg_win_loss(trades)
    psr_value = _calculate_psr(returns)
    
    # alpha and beta (using S&P 500 benchmark)
    alpha, beta = _calculate_alpha_beta(returns, equity_curve.index[0], equity_curve.index[-1])

    ann_var, ann_std = _calculcate_var_std(returns)
    

# TODO: add longest drawdown recovery
    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        total_orders=len(trades),
        sortino=sortino_ratio,
        alpha=alpha,
        beta=beta,
        psr=psr_value,
        avg_win=avg_win,
        avg_loss=avg_loss,
        annualized_variance=ann_var,
        annualized_std = ann_std
    )

# TODO: get more precise daily_rf
def _calculate_sharpe(returns: pd.Series) -> float:
    """Calculate Sharpe ratio assuming 252 trading days and 3.5% risk-free rate."""
    if len(returns) > 1 and returns.std() > 0:
        daily_rf = 0.035 / 252
        return np.sqrt(252) * (returns.mean() - daily_rf) / returns.std()
    return 0.0

# TODO: get more precise daily_rf
def _calculate_sortino(returns: pd.Series) -> float:
    """Calculate Sortino ratio (uses downside deviation instead of std dev)."""
    if len(returns) < 2:
        return 0.0
    
    daily_rf = 0.035 / 252
    excess_returns = returns - daily_rf
    
    # downside deviation: std of negative returns only
    downside_returns = excess_returns[excess_returns < 0]
    if len(downside_returns) == 0 or downside_returns.std() == 0:
        return 0.0
    
    downside_deviation = downside_returns.std()
    return np.sqrt(252) * excess_returns.mean() / downside_deviation


def _calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """Calculate maximum drawdown from peak."""
    if len(equity_curve) < 2:
        return 0.0
    
    running_max = equity_curve.expanding().max()
    drawdown = (equity_curve - running_max) / running_max
    return float(drawdown.min() * -1)


def _calculate_win_rate(trades: List[Trade]) -> float:
    """Calculate win rate based on realized P&L of closed positions."""
    if not trades:
        return 0.0
    
    position_pnl = {}  # symbol: [(buy_price, buy_qty), ...]
    winning_trades = 0
    total_closed_trades = 0
    
    for trade in trades:
        symbol = trade.symbol
        if symbol not in position_pnl:
            position_pnl[symbol] = {'buys': [], 'sells': []}
        
        if trade.action.value == 'buy':
            position_pnl[symbol]['buys'].append((trade.price, trade.shares))
        else:  # sell
            position_pnl[symbol]['sells'].append((trade.price, trade.shares))
    
    # P&L for each symbol
    for symbol, sides in position_pnl.items():
        buys = sides['buys']
        sells = sides['sells']
        
        # FIFO matching
        buy_idx = 0
        for sell_price, sell_qty in sells:
            remaining_qty = sell_qty
            
            while remaining_qty > 0 and buy_idx < len(buys):
                buy_price, buy_qty = buys[buy_idx]
                qty_matched = min(remaining_qty, buy_qty)
                
                pnl = (sell_price - buy_price) * qty_matched
                if pnl > 0:
                    winning_trades += 1
                
                total_closed_trades += 1
                
                remaining_qty -= qty_matched
                buy_qty -= qty_matched
                buys[buy_idx] = (buy_price, buy_qty)
                
                if buy_qty == 0:
                    buy_idx += 1
    
    if total_closed_trades == 0:
        return 0.0
    
    return winning_trades / total_closed_trades


def _calculate_avg_win_loss(trades: List[Trade]) -> Tuple[float, float]:
    """Calculate average win and loss per trade."""
    if not trades:
        return 0.0, 0.0
    
    position_pnl = {}  # symbol: [(buy_price, buy_qty), ...]
    wins = []
    losses = []
    
    for trade in trades:
        symbol = trade.symbol
        if symbol not in position_pnl:
            position_pnl[symbol] = {'buys': [], 'sells': []}
        
        if trade.action.value == 'buy':
            position_pnl[symbol]['buys'].append((trade.price, trade.shares))
        else:  # sell
            position_pnl[symbol]['sells'].append((trade.price, trade.shares))
    
    # P&L for each symbol
    for symbol, sides in position_pnl.items():
        buys = sides['buys']
        sells = sides['sells']
        
        # FIFO matching
        buy_idx = 0
        for sell_price, sell_qty in sells:
            remaining_qty = sell_qty
            
            while remaining_qty > 0 and buy_idx < len(buys):
                buy_price, buy_qty = buys[buy_idx]
                qty_matched = min(remaining_qty, buy_qty)
                
                pnl_per_share = sell_price - buy_price
                pnl_pct = pnl_per_share / buy_price if buy_price != 0 else 0
                
                if pnl_pct > 0:
                    wins.append(pnl_pct)
                elif pnl_pct < 0:
                    losses.append(pnl_pct)
                
                remaining_qty -= qty_matched
                buy_qty -= qty_matched
                buys[buy_idx] = (buy_price, buy_qty)
                
                if buy_qty == 0:
                    buy_idx += 1
    
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = np.mean(losses) if losses else 0.0
    
    return float(avg_win), float(avg_loss)



def _calculate_psr(returns: pd.Series, risk_free_rate: float = 0.035, periods_per_year: int = 252, sr_benchmark: float = 0.0) -> float:
    """
    Probabilistic Sharpe Ratio, returns probability in [0, 1].
    """

    r = returns.dropna()
    T = len(r)

    if T < 2:
        return 0.0

    # Sharpe (annualized)
    daily_rf = risk_free_rate / periods_per_year
    excess = r - daily_rf

    mu = excess.mean()
    sigma = excess.std(ddof=1)

    if sigma == 0:
        return 0.0

    sr_hat = (mu / sigma) * np.sqrt(periods_per_year)

    skew = r.skew()
    kurt = r.kurtosis() + 3  # pandas returns excess kurtosis

    # standard error of Sharpe ratio
    sr_std = np.sqrt(
        (1 - skew * sr_hat + ((kurt - 1) / 4.0) * sr_hat**2) / (T - 1)
    )

    if sr_std <= 0 or np.isnan(sr_std):
        return 0.0

    z = (sr_hat - sr_benchmark) / sr_std

    # Normal CDF
    psr = 0.5 * (1.0 + erf(z / sqrt(2.0)))

    return float(psr)



def _calculate_alpha_beta(returns: pd.Series, start_date: datetime, end_date: datetime) -> Tuple[float, float]:
    """
    Calculate alpha and beta against S&P 500 benchmark.
    """
    try:
        # Download benchmark data
        spy = yf.download('^GSPC', start=start_date, end=end_date+timedelta(days=1), progress=False)

        close = spy["Close"].squeeze("columns")
        benchmark_returns = close.pct_change().dropna()

        aligned_returns, aligned_benchmark = returns.align(benchmark_returns, join="inner")
        
        if len(aligned_returns) < 2:
            return 0.0, 0.0
        
        # beta
        covariance = np.cov(aligned_returns, aligned_benchmark)[0][1]
        benchmark_variance = np.var(aligned_benchmark)
        beta = covariance / benchmark_variance if benchmark_variance != 0 else 0.0
        
        # alpha (annualized)
        strategy_annual_return = (1 + aligned_returns.mean()) ** 252 - 1
        benchmark_annual_return = (1 + aligned_benchmark.mean()) ** 252 - 1
        risk_free_rate = 0.035
        alpha = strategy_annual_return - (risk_free_rate + beta * (benchmark_annual_return - risk_free_rate))
        
        return float(alpha), float(beta)
    
    except Exception as e:
        print(e)
        return -1, -1
    

def _calculcate_var_std(returns: pd.Series, periods_per_year: int = 252) -> Tuple[float, float]:
    clean_returns = returns.dropna()
    
    period_var = clean_returns.var()
    period_std = clean_returns.std()
    
    # Annualize (std scales with sqrt)
    annualized_var = period_var * periods_per_year
    annualized_std = period_std * (periods_per_year ** 0.5)
    
    return annualized_var, annualized_std
