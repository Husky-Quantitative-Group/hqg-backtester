from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class OrderType(str, Enum):
    SELL = "Sell"
    BUY = "Buy"


class Trade(BaseModel):
    """Individual trade/order"""
    id: str
    timestamp: datetime
    ticker: str
    type: OrderType
    price: float
    shares: float


class PerformanceMetrics(BaseModel):
    """Performance metrics for the backtest"""
    # ── equity stats ──
    final_portfolio_value: float = Field(..., description="Final equity value")
    fees: float = Field(..., description="Total fees paid")
    net_profit: float = Field(..., description="Net profit (final - initial)")
    volume: float = Field(..., description="Total trading volume")

    # ── ratios ──
    sharpe: float = Field(..., description="Risk-adjusted return per unit of volatility")
    sortino: float = Field(..., description="Risk-adjusted return per unit of downside volatility")
    calmar: Optional[float] = Field(None, description="Annualized return divided by max drawdown")
    omega: float = Field(..., description="Probability-weighted ratio of gains to losses (threshold=0)")
    treynor: Optional[float] = Field(None, description="Excess return per unit of systematic risk (beta)")
    psr: float = Field(..., description="Probability that the estimated Sharpe ratio exceeds one")

    # ── return ──
    total_pct_return: float = Field(..., description="Total return as a percentage of starting equity")
    annualized_return: Optional[float] = Field(None, description="Total return scaled to a one-year period")
    best_day: float = Field(..., description="Best single-period return")
    worst_day: float = Field(..., description="Worst single-period return")
    avg_daily_return: float = Field(..., description="Mean per-period return")

    # ── risk ──
    ann_vol: float = Field(..., description="Annualized standard deviation of returns")
    max_drawdown: float = Field(..., description="Largest peak-to-trough decline as a percentage")
    max_drawdown_duration: int = Field(..., description="Longest period from peak to recovery in bars")
    var_95: float = Field(..., description="Maximum expected loss at 95% confidence over one period")
    cvar_95: float = Field(..., description="Expected loss in the worst 5% of scenarios")
    skewness: float = Field(..., description="Asymmetry of the return distribution")
    excess_kurtosis: float = Field(..., description="Tailedness of the return distribution relative to normal")
    tail_ratio: float = Field(..., description="Ratio of 95th percentile to abs(5th percentile) of returns")
    ulcer_index: float = Field(..., description="Root mean square of drawdown percentages")
    ulcer_performance_index: Optional[float] = Field(None, description="Excess return divided by Ulcer Index")
    # TODO: prob_overfit: float = Field(..., description="Estimated probability that performance is due to overfitting") ##
    
    # ── benchmark-relative ──
    alpha: float = Field(..., description="Excess return relative to the benchmark (S&P)")
    beta: float = Field(..., description="Sensitivity of returns to benchmark (S&P) movements")
    information_ratio: Optional[float] = Field(None, description="Active return per unit of tracking error")
    tracking_error: Optional[float] = Field(None, description="Annualized std dev of active returns vs benchmark")

    # ── trade analysis ──
    total_orders: int = Field(..., description="Total number of trades executed")
    winning_trades: int = Field(0, description="Number of profitable trades")
    losing_trades: int = Field(0, description="Number of unprofitable trades")
    win_rate: float = Field(0.0, description="Fraction of trades that were profitable")
    avg_win: float = Field(0.0, description="Average profit on winning trades")
    avg_loss: float = Field(0.0, description="Average loss on losing trades")
    largest_win: float = Field(0.0, description="Largest single trade profit")
    largest_loss: float = Field(0.0, description="Largest single trade loss")
    profit_factor: Optional[float] = Field(None, description="Gross profit divided by gross loss")
    expectancy: float = Field(0.0, description="Expected P&L per trade")


class EquityCandle(BaseModel):
    """OHLC candle for equity curve"""
    time: int = Field(..., description="Unix timestamp in seconds")
    open: float
    high: float
    low: float
    close: float
    
    
class DrawdownPoint(BaseModel):
    """Single point in the drawdown time series"""
    time: int = Field(..., description="Unix timestamp in seconds")
    drawdown: float = Field(..., description="Drawdown as a negative decimal (e.g. -0.15 = -15%)")


class BenchmarkCandle(BaseModel):
    """OHLC candle for the benchmark equity curve (SPY), normalized to starting capital"""
    time: int = Field(..., description="Unix timestamp in seconds")
    open: float
    high: float
    low: float
    close: float
    
    
class MonthlyReturn(BaseModel):
    """Single month's return for the heatmap"""
    year: int = Field(..., description="Calendar year")
    month: int = Field(..., description="Calendar month (1-12)")
    return_pct: float = Field(..., description="Return for this month as a decimal (e.g. 0.05 = +5%)")


class RollingMetricPoint(BaseModel):
    """Single point in the rolling metrics time series"""
    time: int = Field(..., description="Unix timestamp in seconds")
    rolling_sharpe: Optional[float] = Field(None, description="Rolling annualized Sharpe ratio")
    rolling_volatility: Optional[float] = Field(None, description="Rolling annualized volatility")
    rolling_beta: Optional[float] = Field(None, description="Rolling beta vs S&P 500")


class DrawdownEpisode(BaseModel):
    """A distinct peak-to-trough drawdown episode"""
    rank: int = Field(..., description="Rank by severity (1 = worst)")
    peak_date: int = Field(..., description="Unix timestamp of the peak")
    valley_date: int = Field(..., description="Unix timestamp of the trough")
    recovery_date: Optional[int] = Field(None, description="Unix timestamp of recovery, null if not yet recovered")
    depth: float = Field(..., description="Drawdown depth as a negative decimal (e.g. -0.15)")
    duration_bars: int = Field(..., description="Bars from peak to trough")
    recovery_bars: Optional[int] = Field(None, description="Bars from trough to recovery, null if not recovered")


class AnnualReturn(BaseModel):
    """Per-calendar-year return"""
    year: int = Field(..., description="Calendar year")
    return_pct: float = Field(..., description="Return for this year as a decimal (e.g. 0.12 = +12%)")


class MonteCarloFanPoint(BaseModel):
    """Percentile bands at a single time step for the Monte Carlo fan chart"""
    time: int = Field(..., description="Unix timestamp in seconds")
    p5: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    p95: float


class MonteCarloResult(BaseModel):
    """Results of a Monte Carlo bootstrap simulation"""
    fan_chart: list[MonteCarloFanPoint] = Field(default_factory=list)
    terminal_wealth_bins: list[float] = Field(default_factory=list, description="Bin edges for terminal wealth histogram")
    terminal_wealth_counts: list[int] = Field(default_factory=list)
    sharpe_bins: list[float] = Field(default_factory=list)
    sharpe_counts: list[int] = Field(default_factory=list)
    max_dd_bins: list[float] = Field(default_factory=list)
    max_dd_counts: list[int] = Field(default_factory=list)
    calmar_bins: list[float] = Field(default_factory=list)
    calmar_counts: list[int] = Field(default_factory=list)
    prob_positive: float = Field(0.0, description="Fraction of simulations ending above starting equity")
    n_simulations: int = Field(0)


class ReturnDistribution(BaseModel):
    """Histogram and fitted-normal parameters for the return series"""
    bin_edges: list[float] = Field(default_factory=list)
    bin_counts: list[int] = Field(default_factory=list)
    mean: float = 0.0
    std: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0


class StressPeriodResult(BaseModel):
    """Strategy return during a predefined market stress window"""
    name: str = Field(..., description="Name of the stress event")
    start_date: int = Field(..., description="Unix timestamp of period start")
    end_date: int = Field(..., description="Unix timestamp of period end")
    strategy_return: float = Field(..., description="Strategy return during the period as a decimal")
    benchmark_return: Optional[float] = Field(None, description="S&P 500 return during the same period")


class BacktestParameters(BaseModel):
    """User-defined parameters used for the backtest run"""
    name: str
    starting_equity: float
    start_date: datetime
    end_date: datetime


class BacktestResponse(BaseModel):
    """ Backtest response format """
    job_id: str
    parameters: BacktestParameters
    metrics: PerformanceMetrics
    candles: list[EquityCandle]
    orders: list[Trade]
    drawdown_series: list[DrawdownPoint] = Field(default_factory=list, description="Drawdown time series for underwater chart")
    benchmark_candles: list[BenchmarkCandle] = Field(default_factory=list, description="SPY equity curve normalized to starting capital")
    monthly_returns: list[MonthlyReturn] = Field(default_factory=list, description="Year x month return grid for heatmap")
    rolling_metrics: list[RollingMetricPoint] = Field(default_factory=list, description="Rolling Sharpe/vol/beta time series")
    top_drawdowns: list[DrawdownEpisode] = Field(default_factory=list, description="Top-5 worst drawdown episodes")
    annual_returns: list[AnnualReturn] = Field(default_factory=list, description="Per-calendar-year returns")
    monte_carlo: Optional[MonteCarloResult] = Field(None, description="Monte Carlo bootstrap simulation results")
    return_distribution: Optional[ReturnDistribution] = Field(None, description="Return histogram and fitted normal params")
    stress_periods: list[StressPeriodResult] = Field(default_factory=list, description="Strategy returns during predefined stress windows")