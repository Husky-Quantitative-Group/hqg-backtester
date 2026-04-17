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
    
    
def compute_drawdown_series(
    equity_curve_data: Dict[datetime, float],
) -> list:
    """
    Compute the full drawdown time series from an equity curve.
    Returns a list of dicts with 'time' (unix seconds) and 'drawdown' (negative decimal).
    """
    if not equity_curve_data:
        return []

    equity_curve = pd.Series(equity_curve_data)
    running_max = equity_curve.expanding().max()
    drawdown = (equity_curve - running_max) / running_max

    return [
        {
            "time": int(ts.timestamp()) if hasattr(ts, 'timestamp') else int(ts),
            "drawdown": round(float(dd), 6),
        }
        for ts, dd in drawdown.items()
    ]


def compute_benchmark_candles(
    data_provider: BaseDataProvider,
    start_date: datetime,
    end_date: datetime,
    bar_size: BarSize,
    initial_capital: float,
) -> list:
    """
    Fetch SPY OHLCV data and normalize it to an equity curve starting at initial_capital.
    Returns a list of dicts matching the BenchmarkCandle schema.
    """
    try:
        df = data_provider.get_data(
            symbols=['^GSPC'],
            start_date=start_date,
            end_date=end_date,
            bar_size=bar_size,
        )

        close = df[('^GSPC', 'close')]
        opn = df[('^GSPC', 'open')] if ('^GSPC', 'open') in df.columns else close
        high = df[('^GSPC', 'high')] if ('^GSPC', 'high') in df.columns else close
        low = df[('^GSPC', 'low')] if ('^GSPC', 'low') in df.columns else close

        if close.empty:
            return []

        # Normalize: scale all prices so the first close equals initial_capital
        scale = initial_capital / close.iloc[0]

        candles = []
        for ts in close.index:
            candles.append({
                "time": int(ts.timestamp()) if hasattr(ts, 'timestamp') else int(ts),
                "open": round(float(opn[ts] * scale), 2),
                "high": round(float(high[ts] * scale), 2),
                "low": round(float(low[ts] * scale), 2),
                "close": round(float(close[ts] * scale), 2),
            })

        return candles

    except Exception as e:
        logger.warning(f"Benchmark candle fetch failed: {e}")
        return []
    
    
def compute_rolling_metrics(
    equity_curve_data: Dict[datetime, float],
    data_provider: BaseDataProvider,
    bar_size: BarSize,
    window: int = 126,
) -> list:
    """
    Compute rolling Sharpe, rolling annualized volatility, and rolling beta
    using a sliding window of `window` bars. Points before the window is full
    are omitted.  All three series share the same timestamps.
    """
    if not equity_curve_data or len(equity_curve_data) < window + 1:
        return []

    equity_curve = pd.Series(equity_curve_data).sort_index()
    returns = equity_curve.pct_change().dropna()

    if len(returns) < window:
        return []

    periods_per_year = _get_periods(bar_size)
    sp500, rf_annual = _get_benchmark_and_rf(
        data_provider, returns.index[0], returns.index[-1], bar_size
    )
    rf_per_period = _per_period_rf(rf_annual, periods_per_year)

    # Rolling Sharpe (vectorized via pandas)
    roll = returns.rolling(window)
    rolling_std = roll.std()
    rolling_mean = roll.mean()
    rolling_sharpe_s = (
        np.sqrt(periods_per_year) * (rolling_mean - rf_per_period) / rolling_std
    ).where(rolling_std > 0)

    # Rolling volatility (annualized)
    rolling_vol_s = rolling_std * np.sqrt(periods_per_year)

    # Rolling beta — requires aligned benchmark returns
    rolling_beta_s = pd.Series(index=returns.index, dtype=float)
    if not sp500.empty:
        bench_rets = sp500.pct_change().dropna()
        aligned_rets, aligned_bench = returns.align(bench_rets, join="inner")
        if len(aligned_rets) >= window:
            roll_cov = aligned_rets.rolling(window).cov(aligned_bench)
            roll_var = aligned_bench.rolling(window).var()
            rolling_beta_s = (roll_cov / roll_var).where(roll_var > 1e-14)

    # Build result list, skipping the first (window-1) NaN entries
    valid_mask = rolling_std.notna()
    results = []
    for ts in returns.index[valid_mask]:
        sharpe_val = rolling_sharpe_s.get(ts)
        vol_val = rolling_vol_s.get(ts)
        beta_val = rolling_beta_s.get(ts) if ts in rolling_beta_s.index else None

        results.append({
            "time": int(ts.timestamp()) if hasattr(ts, "timestamp") else int(ts),
            "rolling_sharpe": None if (sharpe_val is None or np.isnan(sharpe_val)) else round(float(sharpe_val), 6),
            "rolling_volatility": None if (vol_val is None or np.isnan(vol_val)) else round(float(vol_val), 6),
            "rolling_beta": None if (beta_val is None or (isinstance(beta_val, float) and np.isnan(beta_val))) else round(float(beta_val), 6),
        })

    return results


def compute_top_drawdowns(
    equity_curve_data: Dict[datetime, float],
    top_n: int = 5,
) -> list:
    """
    Identify the top-N worst drawdown episodes (peak → valley → recovery).
    Each episode is returned as a dict matching the DrawdownEpisode schema.
    Episodes are ranked from worst depth (rank 1) to least severe.
    """
    if not equity_curve_data or len(equity_curve_data) < 2:
        return []

    equity_curve = pd.Series(equity_curve_data).sort_index()
    running_max = equity_curve.expanding().max()
    drawdown = (equity_curve - running_max) / running_max  # always <= 0

    episodes: list[dict] = []
    in_drawdown = False
    peak_idx = valley_idx = 0

    values = drawdown.values
    index = drawdown.index

    for i, dd in enumerate(values):
        if not in_drawdown:
            if dd < 0:
                in_drawdown = True
                # peak is the last bar where dd was 0
                peak_idx = i - 1 if i > 0 else i
                valley_idx = i
        else:
            if dd < values[valley_idx]:
                valley_idx = i
            if dd >= -1e-10:
                # recovery: record episode
                episodes.append({
                    "peak_idx": peak_idx,
                    "valley_idx": valley_idx,
                    "recovery_idx": i,
                    "depth": float(values[valley_idx]),
                })
                in_drawdown = False

    # If still in drawdown at the end, record without recovery
    if in_drawdown:
        episodes.append({
            "peak_idx": peak_idx,
            "valley_idx": valley_idx,
            "recovery_idx": None,
            "depth": float(values[valley_idx]),
        })

    # Sort by depth (most negative first), take top N
    episodes.sort(key=lambda e: e["depth"])
    episodes = episodes[:top_n]

    def _ts(idx: int) -> int:
        ts = index[idx]
        return int(ts.timestamp()) if hasattr(ts, "timestamp") else int(ts)

    result = []
    for rank, ep in enumerate(episodes, start=1):
        pi, vi, ri = ep["peak_idx"], ep["valley_idx"], ep["recovery_idx"]
        duration_bars = vi - pi
        recovery_bars = (ri - vi) if ri is not None else None
        result.append({
            "rank": rank,
            "peak_date": _ts(pi),
            "valley_date": _ts(vi),
            "recovery_date": _ts(ri) if ri is not None else None,
            "depth": round(ep["depth"], 6),
            "duration_bars": duration_bars,
            "recovery_bars": recovery_bars,
        })

    return result


def compute_annual_returns(
    equity_curve_data: Dict[datetime, float],
) -> list:
    """
    Compute per-calendar-year returns from the equity curve.
    Returns a list of dicts with 'year' and 'return_pct'.
    """
    if not equity_curve_data or len(equity_curve_data) < 2:
        return []

    equity_curve = pd.Series(equity_curve_data).sort_index()
    annual_equity = equity_curve.resample("YE").last().dropna()

    if len(annual_equity) < 2:
        return []

    # Include the starting value so the first year return is meaningful
    first_bar = equity_curve.iloc[0]
    first_year_start = pd.Series(
        [first_bar],
        index=[equity_curve.index[0].floor("D") - pd.offsets.YearEnd(1)],
    )
    annual_with_start = pd.concat([first_year_start, annual_equity])
    annual_rets = annual_with_start.pct_change().dropna()

    return [
        {
            "year": int(ts.year),
            "return_pct": round(float(ret), 6),
        }
        for ts, ret in annual_rets.items()
    ]


def compute_monte_carlo(
    equity_curve_data: Dict[datetime, float],
    bar_size: BarSize,
    n_sims: int = 1000,
    block_size: int = 10,
    seed: Optional[int] = None,
) -> dict:
    """
    Circular block bootstrap Monte Carlo simulation.

    Generates `n_sims` synthetic equity paths by resampling overlapping
    blocks of `block_size` returns with replacement (wrapping at the end).
    All path computation is fully vectorized with NumPy — no Python loops
    over simulations.

    Returns a dict matching the MonteCarloResult schema.
    """
    if not equity_curve_data or len(equity_curve_data) < block_size * 2 + 1:
        return {
            "fan_chart": [],
            "terminal_wealth_bins": [],
            "terminal_wealth_counts": [],
            "sharpe_bins": [],
            "sharpe_counts": [],
            "max_dd_bins": [],
            "max_dd_counts": [],
            "calmar_bins": [],
            "calmar_counts": [],
            "prob_positive": 0.0,
            "n_simulations": 0,
        }

    equity_curve = pd.Series(equity_curve_data).sort_index()
    returns = equity_curve.pct_change().dropna()
    n = len(returns)
    periods_per_year = _get_periods(bar_size)

    rng = np.random.default_rng(seed)
    returns_arr = returns.values.astype(np.float64)

    # ── Circular block bootstrap ──────────────────────────────────────────────
    n_blocks = int(np.ceil(n / block_size))
    # start_indices: (n_sims, n_blocks) — each row is one simulation
    start_indices = rng.integers(0, n, size=(n_sims, n_blocks))
    # offsets: (block_size,)
    offsets = np.arange(block_size, dtype=np.int64)
    # all_indices: (n_sims, n_blocks * block_size), wrapped circularly
    all_indices = (
        start_indices[:, :, np.newaxis] + offsets[np.newaxis, np.newaxis, :]
    ) % n
    all_indices = all_indices.reshape(n_sims, -1)[:, :n]  # trim to exact length

    # sim_returns: (n_sims, n)
    sim_returns = returns_arr[all_indices]

    # ── Equity paths ─────────────────────────────────────────────────────────
    # sim_equity: (n_sims, n+1), starting at 1.0
    ones_col = np.ones((n_sims, 1), dtype=np.float64)
    sim_equity = np.hstack([ones_col, np.cumprod(1.0 + sim_returns, axis=1)])

    # ── Fan chart percentiles at each time step ───────────────────────────────
    pct_levels = [5, 10, 25, 50, 75, 90, 95]
    pct_matrix = np.percentile(sim_equity, pct_levels, axis=0)  # (7, n+1)

    # Map time steps back to original timestamps (use equity_curve.index)
    # index[0] = start of first return bar, so fan_chart aligns with returns
    ts_list = [equity_curve.index[0]] + list(returns.index)
    fan_chart = []
    for i, ts in enumerate(ts_list):
        ts_int = int(ts.timestamp()) if hasattr(ts, "timestamp") else int(ts)
        fan_chart.append({
            "time": ts_int,
            "p5": round(float(pct_matrix[0, i]), 6),
            "p10": round(float(pct_matrix[1, i]), 6),
            "p25": round(float(pct_matrix[2, i]), 6),
            "p50": round(float(pct_matrix[3, i]), 6),
            "p75": round(float(pct_matrix[4, i]), 6),
            "p90": round(float(pct_matrix[5, i]), 6),
            "p95": round(float(pct_matrix[6, i]), 6),
        })

    # ── Terminal wealth distribution ──────────────────────────────────────────
    terminal_wealth = sim_equity[:, -1]
    tw_counts, tw_edges = np.histogram(terminal_wealth, bins=50)

    # ── Per-simulation Sharpe ratios ──────────────────────────────────────────
    sim_mean = sim_returns.mean(axis=1)
    sim_std = sim_returns.std(axis=1, ddof=1)
    sharpe_arr = np.where(
        sim_std > 1e-12,
        sim_mean / sim_std * np.sqrt(periods_per_year),
        0.0,
    )
    sharpe_counts, sharpe_edges = np.histogram(sharpe_arr, bins=50)

    # ── Per-simulation max drawdown ───────────────────────────────────────────
    cummax = np.maximum.accumulate(sim_equity, axis=1)
    dd_matrix = (sim_equity - cummax) / cummax
    max_dd_arr = -dd_matrix.min(axis=1)  # positive values
    dd_counts, dd_edges = np.histogram(max_dd_arr, bins=50)

    # ── Per-simulation Calmar ratio ───────────────────────────────────────────
    ann_returns_arr = terminal_wealth ** (periods_per_year / n) - 1.0
    calmar_arr = np.where(
        max_dd_arr > 1e-10,
        ann_returns_arr / max_dd_arr,
        np.nan,
    )
    valid_calmar = calmar_arr[~np.isnan(calmar_arr)]
    if len(valid_calmar) > 0:
        calmar_counts, calmar_edges = np.histogram(valid_calmar, bins=50)
    else:
        calmar_counts, calmar_edges = np.array([]), np.array([])

    prob_positive = float((terminal_wealth > 1.0).mean())

    def _to_list(arr) -> list:
        return [round(float(x), 6) for x in arr]

    return {
        "fan_chart": fan_chart,
        "terminal_wealth_bins": _to_list(tw_edges),
        "terminal_wealth_counts": tw_counts.tolist(),
        "sharpe_bins": _to_list(sharpe_edges),
        "sharpe_counts": sharpe_counts.tolist(),
        "max_dd_bins": _to_list(dd_edges),
        "max_dd_counts": dd_counts.tolist(),
        "calmar_bins": _to_list(calmar_edges),
        "calmar_counts": calmar_counts.tolist() if len(calmar_counts) > 0 else [],
        "prob_positive": round(prob_positive, 6),
        "n_simulations": n_sims,
    }


def compute_return_distribution(
    equity_curve_data: Dict[datetime, float],
    n_bins: int = 50,
) -> dict:
    """
    Compute return histogram and fitted normal distribution parameters.
    Returns a dict matching the ReturnDistribution schema.
    """
    if not equity_curve_data or len(equity_curve_data) < 3:
        return {
            "bin_edges": [],
            "bin_counts": [],
            "mean": 0.0,
            "std": 0.0,
            "skewness": 0.0,
            "kurtosis": 0.0,
        }

    equity_curve = pd.Series(equity_curve_data).sort_index()
    returns = equity_curve.pct_change().dropna()

    if len(returns) < 3:
        return {"bin_edges": [], "bin_counts": [], "mean": 0.0, "std": 0.0, "skewness": 0.0, "kurtosis": 0.0}

    counts, bin_edges = np.histogram(returns.values, bins=n_bins)

    return {
        "bin_edges": [round(float(e), 8) for e in bin_edges],
        "bin_counts": counts.tolist(),
        "mean": round(float(returns.mean()), 8),
        "std": round(float(returns.std()), 8),
        "skewness": round(float(returns.skew()), 6) if len(returns) > 2 else 0.0,
        "kurtosis": round(float(returns.kurtosis()), 6) if len(returns) > 3 else 0.0,
    }


# Predefined stress / crisis windows
_STRESS_PERIODS = [
    {"name": "COVID Crash", "start": datetime(2020, 2, 19), "end": datetime(2020, 3, 23)},
    {"name": "2022 Bear Market", "start": datetime(2022, 1, 3), "end": datetime(2022, 10, 12)},
    {"name": "SVB Crisis", "start": datetime(2023, 3, 8), "end": datetime(2023, 3, 15)},
    {"name": "Aug 2024 Carry Unwind", "start": datetime(2024, 7, 31), "end": datetime(2024, 8, 5)},
]


def compute_stress_periods(
    equity_curve_data: Dict[datetime, float],
    data_provider: BaseDataProvider,
    bar_size: BarSize,
) -> list:
    """
    Compute strategy and benchmark returns during predefined market stress windows.
    Only periods that overlap with the backtest date range are included.
    Returns a list of dicts matching the StressPeriodResult schema.
    """
    if not equity_curve_data:
        return []

    equity_curve = pd.Series(equity_curve_data).sort_index()
    backtest_start = equity_curve.index[0]
    backtest_end = equity_curve.index[-1]

    # Fetch benchmark once for all periods
    sp500, _ = _get_benchmark_and_rf(data_provider, backtest_start, backtest_end, bar_size)
    bench_rets = sp500.pct_change().dropna() if not sp500.empty else pd.Series()

    results = []
    for period in _STRESS_PERIODS:
        p_start = pd.Timestamp(period["start"])
        p_end = pd.Timestamp(period["end"])

        # Skip periods with no overlap
        if p_end < backtest_start or p_start > backtest_end:
            continue

        # Clip to backtest range
        clip_start = max(p_start, backtest_start)
        clip_end = min(p_end, backtest_end)

        # Strategy return: first/last equity value within the window
        window_equity = equity_curve[clip_start:clip_end]
        if len(window_equity) < 2:
            continue
        strategy_return = float(window_equity.iloc[-1] / window_equity.iloc[0] - 1.0)

        # Benchmark return over same window
        benchmark_return: Optional[float] = None
        if not bench_rets.empty:
            window_bench = bench_rets[clip_start:clip_end]
            if len(window_bench) > 0:
                benchmark_return = round(float((1 + window_bench).prod() - 1.0), 6)

        results.append({
            "name": period["name"],
            "start_date": int(p_start.timestamp()) if hasattr(p_start, "timestamp") else int(p_start),
            "end_date": int(p_end.timestamp()) if hasattr(p_end, "timestamp") else int(p_end),
            "strategy_return": round(strategy_return, 6),
            "benchmark_return": benchmark_return,
        })

    return results


def compute_monthly_returns(
    equity_curve_data: Dict[datetime, float],
) -> list:
    """
    Compute monthly returns from the equity curve for a year x month heatmap.
    Returns a list of dicts with 'year', 'month', and 'return_pct'.
    """
    if not equity_curve_data:
        return []

    equity_curve = pd.Series(equity_curve_data).sort_index()

    # Resample to month-end values, then compute percent change
    monthly_equity = equity_curve.resample('ME').last().dropna()

    if len(monthly_equity) < 2:
        return []

    monthly_rets = monthly_equity.pct_change().dropna()

    return [
        {
            "year": int(ts.year),
            "month": int(ts.month),
            "return_pct": round(float(ret), 6),
        }
        for ts, ret in monthly_rets.items()
    ]