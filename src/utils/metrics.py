# src.utils.metrics
import numpy as np
import pandas as pd
from typing import List
from ..models.portfolio import Portfolio
from ..models.response import Trade, PerformanceMetrics

# TODO: make sharpe ratio calc more robust (fr = avg 10 year tbill return across test timeline)
# TODO: add alpha/beta/etc calcs from S&P returns
# TODO: don't build equity curve twice

def calculate_equity_curve(trades: List[Trade], initial_capital: float):
    return _build_equity_curve(trades, initial_capital)

# TODO: finish
def calculate_metrics(portfolio: Portfolio, trades: List[Trade], initial_capital: float) -> PerformanceMetrics:

    equity_curve = _build_equity_curve(trades, initial_capital)
    returns = equity_curve.pct_change().dropna()
    
    # total return
    final_value = equity_curve.iloc[-1] if len(equity_curve) > 0 else initial_capital
    total_return = (final_value - initial_capital) / initial_capital
    
    # annualized return
    if len(equity_curve) > 1:
        days = (equity_curve.index[-1] - equity_curve.index[0]).days
        years = max(days / 365.25, 1/365.25)  # at least 1 day
        annualized_return = (1 + total_return) ** (1 / years) - 1
    else:
        annualized_return = 0.0
        
    sharpe_ratio = _calculate_sharpe(returns)
    max_drawdown = _calculate_max_drawdown(equity_curve)
    win_rate = _calculate_win_rate(trades)
    
    # + placeholders
    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        total_orders = len(trades),
        sortino = -1,
        alpha = -1,
        beta = -1,
        psr = -1,
        avg_win = -1,
        avg_loss = -1,
    )


def _calculate_sharpe(returns: pd.Series[float]) -> float:
    # (assuming 252 trading days, avg 3.5% risk-free rate...)
    if len(returns) > 1 and returns.std() > 0:
        daily_rf = 0.035 / 252
        return np.sqrt(252) * (returns.mean() - daily_rf) / returns.std()
    return 0.0


def _build_equity_curve(trades: List[Trade], initial_capital: float) -> pd.Series:
    if not trades:
        return pd.Series([initial_capital])
    
    trade_df = pd.DataFrame([
        {
            'timestamp': t.timestamp,
            'value': t.value if t.action == 'sell' else -t.value
        }
        for t in trades
    ])
    
    cash_flows = trade_df.groupby('timestamp')['value'].sum()
    equity = initial_capital + cash_flows.cumsum()
    
    return equity


def _calculate_max_drawdown(equity_curve: pd.Series) -> float:
    if len(equity_curve) < 2:
        return 0.0
    
    running_max = equity_curve.expanding().max()
    drawdown = (equity_curve - running_max) / running_max
    return abs(drawdown.min())


# TODO: placeholder
def _calculate_win_rate(trades: List[Trade]) -> float:
    return .5

# TODO ... add the others (need to get S&P, 10yr T-bill data)