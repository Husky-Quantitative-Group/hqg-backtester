import logging
from ..models.request import BacktestRequest
from ..models.response import BacktestResponse
from ..utils.strategy_loader import StrategyLoader
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
            
            result = await self.backtester.run(
                strategy=strategy,
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=request.initial_capital
            )
            
            logger.info(f"Backtest complete. Final Sharpe: ${result.metrics.sharpe_ratio:.2f}")
            
            return BacktestResponse(
                trades=result.trades,
                metrics=result.metrics,
                equity_curve=result.equity_curve,
                final_value=result.final_value,
                final_holdings=result.final_holdings,
                final_cash=result.final_cash
            )
            
        except Exception as e:
            logger.error(f"Backtest failed: {str(e)}", exc_info=True)
            raise
            
        finally:
            # cleanup strat file
            if strategy_id:
                self.strategy_loader.cleanup_strategy(strategy_id)
                logger.debug(f"Cleaned up strategy {strategy_id}")

    # TODO
    # async def handle_advanced_backtest(self, request):
        # pass