# src.utils.metrics
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from datetime import datetime
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


def _get_periods(bar_size: BarSize) -> int:
    return _PERIODS_PER_YEAR.get(bar_size, 252)

def _per_period_rf(rf_annual: float, periods_per_year: int) -> float:
    """Risk-free rate per bar period."""
    return rf_annual / periods_per_year

def _get_benchmark_and_rf(data_provider: BaseDataProvider, start_date: datetime, end_date: datetime, bar_size: BarSize) -> Tuple[pd.Series, float]:
    """
        Fetch benchmark (S&P 500) and risk-free rate series from data provider.
        Single call to data provider (worse case only single call to yf).
    """
    try:
        df = data_provider.get_data(
            symbols=['^GSPC', '^IRX'],  # S&P 500 and 3-month T-bill as risk-free proxy
            start_date=start_date,
            end_date=end_date,
            bar_size=bar_size,         # same cadence as strategy
        )
        sp500_df = df[('^GSPC', 'close')]
        rf_df = df[('^IRX', 'close')]

        rf_annual = rf_df.mean() / 100.0  # convert to decimal, IRX is in %

        return sp500_df, rf_annual
    
    except Exception as e:
        logger.warning(f"Benchmark/RF fetch failed. Skipping alpha/beta. Default rf = 3.5%. Error: {e}")
        return pd.Series(), 0.035


def calculate_metrics(
        equity_curve_data: Dict[datetime, float],
        trades: List[Trade],
        initial_capital: float,
        data_provider: BaseDataProvider,
        bar_size: BarSize = BarSize.DAILY,
    ) -> PerformanceMetrics:

    # empty equity curve
    if not equity_curve_data:
        logger.warning("Empty equity_curve_data; returning metrics set to zero.")
        return PerformanceMetrics(
            final_portfolio_value=initial_capital,
            fees=0,
            net_profit=0.0,
            volume=0.0,
            sharpe=0.0,
            sortino=0.0,
            calmar=0.0,
            omega=1.0,
            treynor=None,
            psr=0.0,
            total_pct_return=0.0,
            annualized_return=0.0,
            best_day=0.0,
            worst_day=0.0,
            avg_daily_return=0.0,
            ann_vol=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            var_95=0.0,
            cvar_95=0.0,
            skewness=0.0,
            excess_kurtosis=0.0,
            tail_ratio=0.0,
            ulcer_index=0.0,
            ulcer_performance_index=None,
            alpha=0.0,
            beta=0.0,
            information_ratio=None,
            tracking_error=None,
            total_orders=len(trades),
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            largest_win=0.0,
            largest_loss=0.0,
            profit_factor=None,
            expectancy=0.0,
        )

    equity_curve = pd.Series(equity_curve_data)
    periods_per_year = _get_periods(bar_size)
  
    sp500, rf_annual = _get_benchmark_and_rf(data_provider, equity_curve.index[0], equity_curve.index[-1], bar_size)
    rf_per_period = _per_period_rf(rf_annual, periods_per_year)

    returns = equity_curve.pct_change().dropna()

    # total return
    final_value = equity_curve.iloc[-1] if len(equity_curve) > 0 else initial_capital
    total_return = (final_value - initial_capital) / initial_capital

    # annualized return
    annualized_return = _calculate_annualized_return(returns, periods_per_year)
    sharpe_ratio = _calculate_sharpe(returns, periods_per_year, rf_per_period)
    sortino_ratio = _calculate_sortino(returns, periods_per_year, rf_per_period)
    max_drawdown, max_drawdown_duration = _calculate_max_drawdown_and_duration(equity_curve)
    
    calmar_ratio = (annualized_return / max_drawdown) if (annualized_return is not None and max_drawdown > 0) else None

    psr_value = _calculate_psr(returns, periods_per_year, rf_per_period, 1.0)
    volatility = returns.std() * np.sqrt(periods_per_year)

    # alpha and beta (S&P 500 benchmark)
    alpha, beta = _calculate_alpha_beta(returns, periods_per_year, rf_annual, sp500)

    var_95 = np.percentile(returns, 5)
    cvar_95 = returns[returns <= var_95].mean() if (returns <= var_95).any() else var_95

    # ── NEW: expanded metrics ──
    omega = _calculate_omega(returns, threshold=0.0)

    treynor = None
    if annualized_return is not None and abs(beta) > 0.01:
        treynor = (annualized_return - rf_annual) / beta

    best_day = float(returns.max()) if len(returns) > 0 else 0.0
    worst_day = float(returns.min()) if len(returns) > 0 else 0.0
    avg_daily_return = float(returns.mean()) if len(returns) > 0 else 0.0

    skewness = float(returns.skew()) if len(returns) > 2 else 0.0
    excess_kurtosis = float(returns.kurtosis()) if len(returns) > 3 else 0.0

    p95 = np.percentile(returns, 95) if len(returns) > 0 else 0.0
    p5_abs = abs(np.percentile(returns, 5)) if len(returns) > 0 else 0.0
    tail_ratio = float(p95 / p5_abs) if p5_abs > 1e-12 else 0.0

    ulcer = _calculate_ulcer_index(equity_curve)
    upi = None
    if annualized_return is not None and ulcer > 1e-12:
        upi = (annualized_return - rf_annual) / (ulcer / 100.0)  # ulcer is in pct

    info_ratio, tracking_err = _calculate_information_ratio_and_tracking_error(
        returns, sp500, periods_per_year
    )

    trade_stats = _calculate_trade_stats(trades)

    return PerformanceMetrics(
        final_portfolio_value=final_value,
        fees=0,  # TODO: track fees in backtest
        net_profit=final_value - initial_capital,
        volume=sum(t.price * t.shares for t in trades),
        sharpe=sharpe_ratio,
        sortino=sortino_ratio,
        calmar=calmar_ratio,
        omega=omega,
        treynor=treynor,
        psr=psr_value,
        total_pct_return=total_return,
        annualized_return=annualized_return if annualized_return is not None else None,
        best_day=best_day,
        worst_day=worst_day,
        avg_daily_return=avg_daily_return,
        ann_vol=volatility,
        max_drawdown=max_drawdown,
        max_drawdown_duration=max_drawdown_duration,
        var_95=var_95,
        cvar_95=cvar_95,
        skewness=skewness,
        excess_kurtosis=excess_kurtosis,
        tail_ratio=tail_ratio,
        ulcer_index=ulcer,
        ulcer_performance_index=upi,
        alpha=alpha,
        beta=beta,
        information_ratio=info_ratio,
        tracking_error=tracking_err,
        total_orders=len(trades),
        **trade_stats,
    )


def _calculate_sharpe(returns: pd.Series, periods_per_year: int, rf_per_period: float) -> float:
    """
    Annualized Sharpe ratio.

    SR = sqrt(N) * (mean(r) - rf_per_period) / std(r)
    where N = periods_per_year.
    """
    if len(returns) > 1 and returns.std() > 0:
        return float(np.sqrt(periods_per_year) * (returns.mean() - rf_per_period) / returns.std())
    return 0.0


_MIN_OBS_ANNUALIZED = 4
 
def _calculate_annualized_return(returns: pd.Series, periods_per_year: int) -> Optional[float]:
    """Calculate geometric annualized return. Returns None when too few observations."""
    if len(returns) < _MIN_OBS_ANNUALIZED:
        logger.warning(f"Only {len(returns)} returns; annualized return unreliable.")
        return None
 
    return float((1 + returns).prod() ** (periods_per_year / len(returns)) - 1)


def _calculate_sortino(returns: pd.Series, periods_per_year: int, rf_per_period: float) -> float:
    """
    Annualized Sortino ratio.

    Sortino = sqrt(N) * mean(r - rf) / DD
    where DD = sqrt(mean(min(r - rf, 0)^2)) is the downside deviation.
    """
    if len(returns) < 2:
        return 0.0

    excess_returns = returns - rf_per_period

    downside = np.minimum(excess_returns, 0)
    dd = np.sqrt((downside ** 2).mean())

    if dd == 0:
        return 0.0

    return float(np.sqrt(periods_per_year) * excess_returns.mean() / dd)


def _calculate_max_drawdown_and_duration(equity_curve: pd.Series) -> Tuple[float, int]:
    """Calculate maximum drawdown from peak and duration."""
    if len(equity_curve) < 2:
        return 0.0, 0

    running_max = equity_curve.expanding().max()
    drawdown = (equity_curve - running_max) / running_max

    max_duration = 0
    current_duration = 0

    for dd in drawdown:
        if dd < 0:
            current_duration += 1
            max_duration = max(max_duration, current_duration)
        else:
            current_duration = 0

    return float(abs(drawdown.min())), max_duration


def _calculate_psr(
    returns: pd.Series,
    periods_per_year: int,
    rf_per_period: float,
    sr_benchmark: float,
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

    excess = r - rf_per_period

    mu = excess.mean()
    sigma = excess.std(ddof=1)

    if sigma == 0:
        return 0.0

    sr_hat = (mu / sigma) * np.sqrt(periods_per_year)

    skew = r.skew()
    excess_kurt = r.kurtosis()

    # Standard error of Sharpe ratio (Lo 2002)
    sr_std = np.sqrt(
        (1 - skew * sr_hat + ((excess_kurt - 1) / 4.0) * sr_hat ** 2) / (T - 1)
    )

    if sr_std <= 0 or np.isnan(sr_std):
        return 0.0

    z = (sr_hat - sr_benchmark) / sr_std

    # Normal CDF via error function
    psr = 0.5 * (1.0 + erf(z / sqrt(2.0)))

    return float(psr)

def _calculate_alpha_beta(returns: pd.Series, periods_per_year: int, rf_annual: float, sp500: pd.Series) -> Tuple[float, float]:
    """
    Calculate CAPM alpha and beta against S&P 500 benchmark.

    When a data_provider is available the benchmark is fetched (and
    resampled) through the same pipeline as strategy data, ensuring the
    bar sizes match. The raw yfinance fallback fetches daily data and
    resamples manually so the periods still align.
    """
    
    benchmark_returns = sp500.pct_change().dropna()
    aligned_returns, aligned_benchmark = returns.align(benchmark_returns, join="inner")

    # warn when alignment drops a significant fraction of data
    if len(returns) > 0:
        dropped_frac = 1.0 - len(aligned_returns) / len(returns)
        if dropped_frac > 0.05:
            logger.warning(
                f"Benchmark alignment dropped {dropped_frac:.1%} of strategy "
                f"returns ({len(returns)} -> {len(aligned_returns)} observations)."
            )

    if len(aligned_returns) < _MIN_OBS_ANNUALIZED:
        return 0.0, 0.0

    # beta = Cov(r_s, r_b) / Var(r_b) = covmtx[0][1] / covmtx[1][1]
    cov_matrix = np.cov(aligned_returns, aligned_benchmark)
    beta = cov_matrix[0][1] / cov_matrix[1][1]

    # alpha
    strategy_annual_return = (1 + aligned_returns.mean()) ** periods_per_year - 1
    benchmark_annual_return = (1 + aligned_benchmark.mean()) ** periods_per_year - 1
    alpha = strategy_annual_return - (rf_annual + beta * (benchmark_annual_return - rf_annual))

    return float(alpha), float(beta)


def _calculate_omega(returns: pd.Series, threshold: float = 0.0) -> float:
    """
    Omega ratio: sum of returns above threshold / sum of returns below threshold.
    Keating & Shadwick (2002).
    """
    excess = returns - threshold
    gains = excess[excess > 0].sum()
    losses = -excess[excess < 0].sum()
    if losses < 1e-12:
        return 99.0
    return float(gains / losses)


def _calculate_ulcer_index(equity_curve: pd.Series) -> float:
    """
    Ulcer Index: RMS of percentage drawdowns.
    Martin & McCann (1987).
    """
    if len(equity_curve) < 2:
        return 0.0
    running_max = equity_curve.expanding().max()
    dd_pct = ((equity_curve - running_max) / running_max) * 100.0
    return float(np.sqrt((dd_pct ** 2).mean()))


def _calculate_information_ratio_and_tracking_error(
    returns: pd.Series,
    sp500: pd.Series,
    periods_per_year: int,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Information Ratio = mean(active_return) / std(active_return) * sqrt(N)
    Tracking Error = annualized std dev of active returns.
    """
    benchmark_returns = sp500.pct_change().dropna()
    aligned_strat, aligned_bench = returns.align(benchmark_returns, join="inner")

    if len(aligned_strat) < _MIN_OBS_ANNUALIZED:
        return None, None

    active = aligned_strat - aligned_bench
    te = float(active.std() * np.sqrt(periods_per_year))

    if te < 1e-12:
        return None, te

    ir = float(active.mean() * np.sqrt(periods_per_year) / active.std())
    return ir, te


def _calculate_trade_stats(trades: List[Trade]) -> dict:
    """
    Compute trade-level statistics: win rate, avg win/loss, largest win/loss,
    profit factor, and expectancy.
    
    Groups trades into round-trip pairs (buy then sell for same ticker) and
    computes P&L per round trip. If no complete round trips exist, falls back
    to per-trade signed P&L estimation.
    """
    if not trades:
        return {
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "profit_factor": None,
            "expectancy": 0.0,
        }

    # Build round-trip P&Ls by matching buys to subsequent sells per ticker
    from collections import defaultdict, deque

    open_positions: Dict[str, deque] = defaultdict(deque)  # ticker -> deque of (price, shares)
    pnls: List[float] = []

    for t in sorted(trades, key=lambda x: x.timestamp):
        if t.type.value == "Buy":
            open_positions[t.ticker].append((t.price, t.shares))
        elif t.type.value == "Sell":
            remaining = t.shares
            while remaining > 0 and open_positions[t.ticker]:
                entry_price, entry_shares = open_positions[t.ticker][0]
                closed = min(remaining, entry_shares)
                pnl = (t.price - entry_price) * closed
                pnls.append(pnl)
                remaining -= closed
                if closed >= entry_shares:
                    open_positions[t.ticker].popleft()
                else:
                    open_positions[t.ticker][0] = (entry_price, entry_shares - closed)

    if not pnls:
        return {
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "profit_factor": None,
            "expectancy": 0.0,
        }

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_profit = sum(wins) if wins else 0.0
    gross_loss = -sum(losses) if losses else 0.0

    return {
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": len(wins) / len(pnls) if pnls else 0.0,
        "avg_win": gross_profit / len(wins) if wins else 0.0,
        "avg_loss": sum(losses) / len(losses) if losses else 0.0,
        "largest_win": max(pnls) if pnls else 0.0,
        "largest_loss": min(pnls) if pnls else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss > 1e-12 else None,
        "expectancy": sum(pnls) / len(pnls) if pnls else 0.0,
    }