from datetime import datetime
from .engine.backtester import Backtester


def run_backtest_engine(
    algorithm_class,
    universe: list[str],
    start_date: datetime,
    end_date: datetime,
    initial_cash: float | None = 10000.0,
    data_path: str | None = None,
    commission_rate: float=0.005,
):
    backtester = Backtester(
        data_path=data_path,
        algorithm_class=algorithm_class,
        initial_cash=10000.0 if initial_cash is None else float(initial_cash),
        commission_rate=commission_rate
    )
    
    results = backtester.run_backtest(
        start_date=start_date,
        end_date=end_date,
        symbols=universe
    )
    
    return results

