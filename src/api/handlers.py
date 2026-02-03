import logging
from datetime import datetime
from ..models.request import BacktestRequest
from ..models.response import (
    BacktestResponse,
    BacktestParameters,
    EquityStats,
    EquityCandle,
    Trade,
)
from ..utils.strategy_loader import StrategyLoader
from ..utils.metrics import calculate_metrics
from ..services.backtester import Backtester

logger = logging.getLogger(__name__)


class BacktestHandler:

    def __init__(self):
        self.strategy_loader = StrategyLoader()
        self.backtester = Backtester()

    async def handle_backtest(self, request: BacktestRequest) -> BacktestResponse:

        strategy_id = None

        try:
            logger.info(f"Starting backtest: {request.start_date} to {request.end_date}")

            strategy_class = self.strategy_loader.load_strategy(request.strategy_code)
            strategy = strategy_class()
            strategy_id = str(id(strategy))

            logger.info(f"Loaded strategy with universe: {strategy.universe()}")

            # TODO: Replace with validation pipeline:
            #   analyzed_request = StaticAnalyzer.analyze(request)
            #   raw_result = Executor.execute(analyzed_request)
            #   validated_result = OutputValidator.validate(raw_result)
            #   metrics = calculate_metrics(...)
            #   return transform_to_response(validated_result, metrics, request)

            raw_result = await self.backtester.run(
                strategy=strategy,
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=request.initial_capital
            )

            # Reconstruct Trade objects from raw dicts
            trades = [Trade(**t) for t in raw_result.trades]

            # Parse equity curve keys back to datetime for metrics calculation
            equity_curve_dt = {
                datetime.fromisoformat(ts): val
                for ts, val in raw_result.equity_curve.items()
            }

            # Compute metrics (single source of truth, after execution)
            metrics = calculate_metrics(
                equity_curve_data=equity_curve_dt,
                trades=trades,
                initial_capital=request.initial_capital,
                data_provider=self.backtester.data_provider,
            )

            logger.info(f"Backtest complete. Sharpe: {metrics.sharpe:.2f}")

            # Transform to frontend response format
            net_profit = raw_result.final_value - request.initial_capital
            total_volume = sum(t.price * t.amount for t in trades)

            candles = [
                EquityCandle(
                    time=int(datetime.fromisoformat(ts).timestamp()),
                    **ohlc_vals,
                )
                for ts, ohlc_vals in raw_result.ohlc.items()
            ]

            return BacktestResponse(
                parameters=BacktestParameters(
                    name=request.name or "Unnamed Backtest",
                    starting_equity=request.initial_capital,
                    start_date=request.start_date,
                    end_date=request.end_date,
                ),
                metrics=metrics,
                equity_stats=EquityStats(
                    equity=raw_result.final_value,
                    fees=0.0,  # TODO: implement fee tracking in portfolio
                    net_profit=net_profit,
                    return_pct=metrics.total_return * 100,
                    volume=total_volume,
                ),
                candles=candles,
                orders=trades,
            )

        except Exception as e:
            logger.error(f"Backtest failed: {str(e)}", exc_info=True)
            raise

        finally:
            if strategy_id:
                self.strategy_loader.cleanup_strategy(strategy_id)
                logger.debug(f"Cleaned up strategy {strategy_id}")
