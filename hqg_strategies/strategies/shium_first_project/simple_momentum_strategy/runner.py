import os
from pathlib import Path
import yaml
import logging
from datetime import datetime
from hqg_backtester.engine.backtester import Backtester
from hqg_backtester.data.sources.ibkr import DataManager


def find_repo_root(start_path: str | Path) -> Path:
    p = Path(start_path).resolve()
    for _ in range(10):
        if (p / "pyproject.toml").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path(start_path).resolve()


def run(strategy_class, benchmark: str = None):
    """
    Handles configuration loading, logging setup, and backtest execution.
    Assumes `config.yml` is in the same directory as this script unless overridden.
    
    Args:
        strategy_class: The Algorithm class to run
        benchmark: Optional benchmark symbol for comparison (e.g., "SPY", "QQQ")
    """
    script_dir = Path(__file__).parent
    config_path = script_dir / "config.yml"

    # Load configuration
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Logging
    log_level_raw = config.get("log_level", "INFO")
    log_level = str(log_level_raw).upper()
    logging.basicConfig(level=getattr(logging, log_level))
    logger = logging.getLogger(strategy_class.__name__)

    # Determine data path (default: <repo_root>/data or script_dir/data)
    repo_root = find_repo_root(script_dir)
    default_data_path = repo_root / "data"
    data_path = Path(config.get("data_path", default_data_path))
    if not data_path.exists():
        logger.warning(f"Data path {data_path} does not exist; Backtester may fail to load data.")

    # Parse dates
    start_date = datetime.fromisoformat(config["start_date"]) if "start_date" in config else None
    end_date = datetime.fromisoformat(config["end_date"]) if "end_date" in config else None

    # Auto-pull missing data using DataManager (IBKR)
    try:
        ibkr_host = config.get("ibkr_host", "127.0.0.1")
        ibkr_port = int(config.get("ibkr_port", 7497))
        dm = DataManager(str(data_path), ibkr_host=ibkr_host, ibkr_port=ibkr_port)
        logger.info("Checking and auto-pulling missing symbols via DataManager if needed...")
        pulled = dm.get_data(config.get("symbols", []), start_date, end_date, auto_pull=True)
        if not pulled:
            logger.warning("DataManager did not return any data for requested symbols. Backtester may fail if no local data present.")
    except Exception as e:
        logger.warning(f"DataManager auto-pull failed or unavailable: {e}")

    # Instantiate backtester with appropriate args
    # Note: initial_cash is set by the strategy in Initialize(), not from config
    initial_cash = 100_000.0  # Default fallback
    commission_rate = config.get("commission_rate", 0.005)
    bt = Backtester(
        data_path=data_path,
        algorithm_class=strategy_class,
        initial_cash=initial_cash,
        commission_rate=commission_rate,
        log_level=log_level,
    )

    # Run backtest
    try:
        results = bt.run_backtest(
            start_date=start_date,
            end_date=end_date,
            symbols=config.get("symbols", []),
        )
        
        # Optionally fetch benchmark data for comparison
        if benchmark:
            try:
                logger.info(f"Fetching benchmark data for {benchmark}...")
                benchmark_data = dm.storage.load_daily_data(benchmark)
                
                # If not available locally, try to fetch it
                if benchmark_data is None or benchmark_data.empty:
                    logger.info(f"Benchmark {benchmark} not found locally, fetching...")
                    dm.auto_pull_symbol(benchmark, start_date, end_date)
                    benchmark_data = dm.storage.load_daily_data(benchmark)
                
                # Filter benchmark to backtest date range
                if benchmark_data is not None and not benchmark_data.empty:
                    benchmark_data = benchmark_data[(benchmark_data.index >= start_date) & 
                                                   (benchmark_data.index <= end_date)]
                    
                    # Recalculate performance report with benchmark
                    from hqg_backtester.analysis.metrics import PerformanceMetrics
                    metrics = PerformanceMetrics()
                    results['performance_report'] = metrics.generate_performance_report(
                        equity_curve=results['equity_curve'],
                        fills=results['fills'],
                        initial_cash=initial_cash,
                        benchmark_data=benchmark_data
                    )
                    
                    # Re-format and log summary with benchmark
                    summary = metrics.format_metrics_summary(results['performance_report'])
                    logger.info(f"\n{summary}")
                else:
                    logger.warning(f"Could not load benchmark data for {benchmark}")
                    
            except Exception as e:
                logger.warning(f"Failed to fetch benchmark data: {e}")
        
        logger.info("Backtest finished successfully")
        return results
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise