from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict
from enum import Enum


class OrderType(str, Enum):
    SELL = "sell"
    BUY = "buy"

class Trade(BaseModel):
    timestamp: datetime
    symbol: str
    action: OrderType
    shares: float
    price: float
    value: float    # redundant?


# TODO: make more robust?
class PerformanceMetrics(BaseModel):
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_orders: int
    sortino: float
    alpha: float
    beta: float
    psr: float
    avg_win: float
    avg_loss: float


# In case we want extra stuff that won't appear in dashboard
class BacktestResult(BaseModel):
    """Backtest result (used internally)"""
    trades: List[Trade]
    metrics: PerformanceMetrics
    final_value: float
    final_holdings: Dict[str, float]
    final_cash: float


class BacktestResponse(BaseModel):
    """API response format"""
    trades: List[Trade]
    metrics: PerformanceMetrics
    final_value: float
    final_holdings: Dict[str, float]
    final_cash: float