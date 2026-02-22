# src.utils.metrics
import numpy as np
import pandas as pd
import yfinance as yf
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from hqg_algorithms import BarSize
from ..models.response import Trade, PerformanceMetrics
from ..services.data_provider.base_provider import BaseDataProvider
from math import erf, sqrt

import logging

logger = logging.getLogger(__name__)

# trading periods per year for each bar size.
_PERIODS_PER_YEAR = {
    BarSize.DAILY: 252,
    BarSize.WEEKLY: 52,
    BarSize.MONTHLY: 12,
    BarSize.QUARTERLY: 4,
}

# TODO: make this dynamic (avg 10yr T-bill across test timeline)
_ANNUAL_RISK_FREE_RATE = 0.035


def _get_periods(bar_size: BarSize) -> int:
    return _PERIODS_PER_YEAR.get(bar_size, 252)

def _per_period_rf(periods_per_year: int) -> float:
    """Risk-free rate per bar period."""
    return _ANNUAL_RISK_FREE_RATE / periods_per_year


def calculate_metrics(
        equity_curve_data: Dict[datetime, float],
        trades: List[Trade],
        initial_capital: float,
        data_provider:BaseDataProvider,
        bar_size: BarSize = BarSize.DAILY,
    ) -> PerformanceMetrics:

    periods_per_year = _get_periods(bar_size)

    equity_curve = pd.Series(equity_curve_data)
    returns = equity_curve.pct_change().dropna()

    # total return
    final_value = equity_curve.iloc[-1] if len(equity_curve) > 0 else initial_capital
    total_return = (final_value - initial_capital) / initial_capital

    # annualized return
    if len(equity_curve) > 1:
        if len(returns) >= max(4, periods_per_year // 4):
            # geometric default
            annualized_return = (1 + returns).prod() ** (periods_per_year / len(returns)) - 1
        else:
            # arithmetic for short horizon
            annualized_return = returns.mean() * periods_per_year
    else:
        annualized_return = 0.0

    sharpe_ratio = _calculate_sharpe(returns, periods_per_year)
    sortino_ratio = _calculate_sortino(returns, periods_per_year)
    max_drawdown = _calculate_max_drawdown(equity_curve)
    win_rate = _calculate_win_rate(trades)
    avg_win, avg_loss = _calculate_avg_win_loss(trades)
    psr_value = _calculate_psr(returns, periods_per_year, sr_benchmark=1.0)

    # alpha and beta (S&P 500 benchmark)
    alpha, beta = _calculate_alpha_beta(
        returns,
        equity_curve.index[0],
        equity_curve.index[-1],
        data_provider,
        bar_size,
        periods_per_year,
    )

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
    )

def _calculate_sharpe(returns: pd.Series, periods_per_year: int) -> float:
    """
    Annualized Sharpe ratio.

    SR = sqrt(N) * (mean(r) - rf_per_period) / std(r)
    where N = periods_per_year.
    """
    if len(returns) > 1 and returns.std() > 0:
        rf = _per_period_rf(periods_per_year)
        return float(np.sqrt(periods_per_year) * (returns.mean() - rf) / returns.std())
    return 0.0

def _calculate_sortino(returns: pd.Series, periods_per_year: int) -> float:
    """
    Annualized Sortino ratio = √(mean(min(r - rf, 0)²))
    """
    if len(returns) < 2:
        return 0.0

    rf = _per_period_rf(periods_per_year)
    excess_returns = returns - rf

    downside = np.minimum(excess_returns, 0)
    dd = np.sqrt((downside ** 2).mean())

    if dd == 0:
        return 0.0

    return float(np.sqrt(periods_per_year) * excess_returns.mean() / dd)


def _calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """Calculate maximum drawdown from peak. Timeframe-agnostic."""
    if len(equity_curve) < 2:
        return 0.0

    running_max = equity_curve.expanding().max()
    drawdown = (equity_curve - running_max) / running_max
    return float(drawdown.min() * -1)

# TODO: currently per-matched-lot, not per-trade
def _calculate_win_rate(trades: List[Trade]) -> float:
    """Calculate win rate based on realized P&L of closed positions (FIFO)."""
    if not trades:
        return 0.0

    position_pnl = {}
    winning_trades = 0
    total_closed_trades = 0

    for trade in trades:
        symbol = trade.ticker
        if symbol not in position_pnl:
            position_pnl[symbol] = {'buys': [], 'sells': []}

        if trade.type.value == 'Buy':
            position_pnl[symbol]['buys'].append((trade.price, trade.amount))
        else:
            position_pnl[symbol]['sells'].append((trade.price, trade.amount))

    for symbol, sides in position_pnl.items():
        buys = sides['buys']
        sells = sides['sells']

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
    """Calculate average win and loss percentage per trade (FIFO)."""
    if not trades:
        return 0.0, 0.0

    position_pnl = {}
    wins = []
    losses = []

    for trade in trades:
        symbol = trade.ticker
        if symbol not in position_pnl:
            position_pnl[symbol] = {'buys': [], 'sells': []}

        if trade.type.value == 'Buy':
            position_pnl[symbol]['buys'].append((trade.price, trade.amount))
        else:
            position_pnl[symbol]['sells'].append((trade.price, trade.amount))

    for symbol, sides in position_pnl.items():
        buys = sides['buys']
        sells = sides['sells']

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

    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0

    return avg_win, avg_loss

def _calculate_psr(
    returns: pd.Series,
    periods_per_year: int,
    risk_free_rate: float = _ANNUAL_RISK_FREE_RATE,
    sr_benchmark: float = 1.0,
) -> float:
    """
    Probabilistic Sharpe Ratio: probability that the true Sharpe exceeds
    sr_benchmark, accounting for skew and kurtosis of the return series.
    Returns a value in [0, 1].
    """
    r = returns.dropna()
    T = len(r)

    if T < 2:
        return 0.0

    rf = risk_free_rate / periods_per_year
    excess = r - rf

    mu = excess.mean()
    sigma = excess.std(ddof=1)

    if sigma == 0:
        return 0.0

    sr_hat = (mu / sigma) * np.sqrt(periods_per_year)

    skew = r.skew()
    kurt = r.kurtosis() + 3  # pandas returns excess kurtosis; convert to raw

    # Standard error of Sharpe ratio (Lo 2002, adjusted for non-normality)
    sr_std = np.sqrt(
        (1 - skew * sr_hat + ((kurt - 1) / 4.0) * sr_hat ** 2) / (T - 1)
    )

    if sr_std <= 0 or np.isnan(sr_std):
        return 0.0

    z = (sr_hat - sr_benchmark) / sr_std

    # Normal CDF via error function
    psr = 0.5 * (1.0 + erf(z / sqrt(2.0)))

    return float(psr)

def _calculate_alpha_beta(
    returns: pd.Series,
    start_date: datetime,
    end_date: datetime,
    data_provider: BaseDataProvider,
    bar_size: BarSize,
    periods_per_year: int,
) -> Tuple[float, float]:
    """
    Calculate CAPM alpha and beta against S&P 500 benchmark.

    When a data_provider is available the benchmark is fetched (and
    resampled) through the same pipeline as strategy data, ensuring the
    bar sizes match. The raw yfinance fallback fetches daily data and
    resamples manually so the periods still align.
    """
    try:
        spy = data_provider.get_data(
            symbols=['^GSPC'],
            start_date=start_date,
            end_date=end_date,
            bar_size=bar_size,         # same cadence as strategy
        )
        close = spy[('^GSPC', 'close')]

        benchmark_returns = close.pct_change().dropna()

        aligned_returns, aligned_benchmark = returns.align(benchmark_returns, join="inner")

        if len(aligned_returns) < 2:
            return 0.0, 0.0

        # beta = Cov(r_s, r_b) / Var(r_b) = covmtx[0][1] / covmtx[1][1]
        cov_matrix = np.cov(aligned_returns, aligned_benchmark)
        beta = cov_matrix[0][1] / cov_matrix[1][1]

        # alpha (annualized via correct periods_per_year)
        strategy_annual_return = (1 + aligned_returns.mean()) ** periods_per_year - 1
        benchmark_annual_return = (1 + aligned_benchmark.mean()) ** periods_per_year - 1
        alpha = strategy_annual_return - (_ANNUAL_RISK_FREE_RATE + beta * (benchmark_annual_return - _ANNUAL_RISK_FREE_RATE))

        return float(alpha), float(beta)

    except Exception as e:
        logger.warning(f"Alpha/beta calculation failed: {e}")
        return -float("inf"), -float("inf")