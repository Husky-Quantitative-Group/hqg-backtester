from datetime import datetime

from .engine.backtester import Backtester


def run(
    algorithm_class,
    universe,
    start_date,
    end_date,
    initial_cash=100000.0,
    benchmark=None,
    data_path=None,
    commission_rate=0.005,
    verbose=False,
):
    backtester = Backtester(
        data_path=data_path,
        algorithm_class=algorithm_class,
        initial_cash=initial_cash,
        commission_rate=commission_rate
    )
    
    results = backtester.run_backtest(
        start_date=start_date,
        end_date=end_date,
        symbols=universe
    )
    
    return results

