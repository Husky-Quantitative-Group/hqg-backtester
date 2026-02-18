from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, List, Any
from ..models.request import BacktestRequestError

class ExecutionPayload(BaseModel):
    strategy_code: str = Field(..., description="Raw Python strategy code to execute", min_length=10)
    name: Optional[str] = Field(default="Unnamed Backtest", description="Name for this backtest run")
    start_date: datetime
    end_date: datetime
    initial_capital: float = Field(default=100000.0, description="Starting cash of Python strategy", gt=0)
    market_data: Dict[str, Any] = Field(..., description="Pre-fetched OHLC data")


class RawExecutionResult(BaseModel):
    trades: List[Dict[str, Any]] = Field(default_factory=list, description="Raw trade data")
    equity_curve: Dict[str, float] = Field(default_factory=dict, description="Timestamp -> equity mapping")
    ohlc: Dict[str, Dict[str, float]] = Field(default_factory=dict, description="Timestamp -> portfolio OHLC")
    final_value: float = Field(..., description="Final portfolio value")
    final_cash: float = Field(..., description="Final cash balance")
    final_positions: Dict[str, float] = Field(default_factory=dict, description="Final positions held")

    execution_time: Optional[float] = Field(default=None, description="Execution time in seconds")
    errors: BacktestRequestError = Field(default_factory=BacktestRequestError, description="Any errors encountered during execution")
