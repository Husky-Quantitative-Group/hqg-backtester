from datetime import datetime
from ..models.request import BacktestRequest
from ..models.execution import RawExecutionResult
from ..models.response import (
    BacktestResponse,
    BacktestParameters,
    EquityCandle,
    Trade,
)
from ..services.data_provider.base_provider import BaseDataProvider
from .metrics import calculate_metrics


def build_backtest_response(
    job_id: str,
    request: BacktestRequest,
    raw_result: RawExecutionResult,
    data_provider: BaseDataProvider,
) -> BacktestResponse:
    
    trades = [Trade(**t) for t in raw_result.orders]

    equity_curve_dt = {
        datetime.fromisoformat(ts): val
        for ts, val in raw_result.equity_curve.items()
    }

    metrics = calculate_metrics(
        equity_curve_data=equity_curve_dt,
        trades=trades,
        initial_capital=request.initial_capital,
        data_provider=data_provider,
        bar_size=raw_result.bar_size,
    )

    candles = [
        EquityCandle(
            time=int(datetime.fromisoformat(ts).timestamp()),
            **ohlc_vals,
        )
        for ts, ohlc_vals in raw_result.ohlc.items()
    ]

    return BacktestResponse(
        job_id=job_id,
        parameters=BacktestParameters(
            name=request.name or "Unnamed Backtest",
            starting_equity=request.initial_capital,
            start_date=request.start_date,
            end_date=request.end_date,
        ),
        metrics=metrics,
        candles=candles,
        orders=trades,
    )