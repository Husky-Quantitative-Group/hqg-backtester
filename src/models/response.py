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
    

    alpha: float = Field(..., description="Excess return relative to the benchmark (S&P)")
    beta: float = Field(..., description="Sensitivity of returns to benchmark (S&P) movements")
    total_orders: int = Field(..., description="Total number of trades executed")


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
