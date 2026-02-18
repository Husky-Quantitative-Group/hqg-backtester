from pydantic import BaseModel, Field
from datetime import datetime
from typing import List
from enum import Enum


class OrderType(str, Enum):
    SELL = "Sell"  # Capitalized to match frontend
    BUY = "Buy"    # Capitalized to match frontend


class Trade(BaseModel):
    """Individual trade/order"""
    id: str
    timestamp: datetime
    ticker: str = Field(..., alias="symbol")
    type: OrderType = Field(..., alias="action")
    price: float
    amount: float = Field(..., alias="shares")

    class Config:
        populate_by_name = True


class PerformanceMetrics(BaseModel):
    """Performance metrics for the backtest"""
    # Core ratios
    sharpe: float = Field(..., alias="sharpe_ratio")
    sortino: float
    alpha: float
    beta: float
    psr: float

    # Returns and drawdown
    total_return: float
    annualized_return: float
    max_drawdown: float

    # Trade statistics
    win_rate: float
    total_orders: int
    avg_win: float
    avg_loss: float

    class Config:
        populate_by_name = True


class EquityStats(BaseModel):
    """Summary statistics for equity curve"""
    equity: float = Field(..., description="Final equity value")
    fees: float = Field(..., description="Total fees paid")
    net_profit: float = Field(..., description="Net profit (final - initial)")
    return_pct: float = Field(..., description="Return as percentage")
    volume: float = Field(..., description="Total trading volume")


class EquityCandle(BaseModel):
    """OHLC candle for equity curve"""
    time: int = Field(..., description="Unix timestamp in seconds")
    open: float
    high: float
    low: float
    close: float


class BacktestParameters(BaseModel):
    """Parameters used for the backtest run"""
    name: str
    starting_equity: float
    start_date: datetime
    end_date: datetime


class BacktestResponse(BaseModel):
    """
    API response format - matches frontend TypeScript structure.
    This is what the React component expects to receive.
    """
    parameters: BacktestParameters
    metrics: PerformanceMetrics
    equity_stats: EquityStats
    candles: List[EquityCandle]
    orders: List[Trade]
