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
    # equity stats
    final_portfolio_value: float = Field(..., description="Final equity value")
    fees: float = Field(..., description="Total fees paid")
    net_profit: float = Field(..., description="Net profit (final - initial)")
    volume: float = Field(..., description="Total trading volume")

    # ratios
    sharpe: float = Field(..., description="Risk-adjusted return per unit of volatility")
    sortino: float = Field(..., description="Risk-adjusted return per unit of downside volatility")
    calmar: Optional[float] = Field(None, description="Annualized return divided by max drawdown")
    psr: float = Field(..., description="Probability that the estimated Sharpe ratio exceeds one")

    # return
    total_pct_return: float = Field(..., description="Total return as a percentage of starting equity")
    annualized_return: Optional[float] = Field(None, description="Total return scaled to a one-year period")

    # risk
    ann_vol: float = Field(..., description="Annualized standard deviation of returns")
    max_drawdown: float = Field(..., description="Largest peak-to-trough decline as a percentage")
    max_drawdown_duration: int = Field(..., description="Longest period from peak to recovery in bars")
    var_95: float = Field(..., description="Maximum expected loss at 95% confidence over one day")
    cvar_95: float = Field(..., description="Expected loss in the worst 5% of scenarios")
    # TODO: prob_overfit: float = Field(..., description="Estimated probability that performance is due to overfitting")

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


class BacktestParameters(BaseModel):
    """User-defined parameters used for the backtest run"""
    name: str
    starting_equity: float
    start_date: datetime
    end_date: datetime

class WeightSnapshot(BaseModel):
    """Portfolio weights at a given point in time"""
    time: int = Field(..., description="Unix timestamp in seconds")
    weights: dict[str, float] = Field(..., description="Ticker -> weight mapping")


class BacktestResponse(BaseModel):
    """ Backtest response format """
    job_id: str
    parameters: BacktestParameters
    metrics: PerformanceMetrics
    orders: list[Trade]
    candles: list[EquityCandle]
    holding_weights: list[WeightSnapshot]
