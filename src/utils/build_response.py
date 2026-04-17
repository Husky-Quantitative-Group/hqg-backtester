from datetime import datetime
from ..models.request import BacktestRequest
from ..models.execution import RawExecutionResult
from ..models.response import (
    BacktestResponse,
    BacktestParameters,
    EquityCandle,
    Trade,
    DrawdownPoint,
    BenchmarkCandle,
    MonthlyReturn,
    RollingMetricPoint,
    DrawdownEpisode,
    AnnualReturn,
    MonteCarloResult,
    MonteCarloFanPoint,
    ReturnDistribution,
    StressPeriodResult,
)
from ..services.data_provider.base_provider import BaseDataProvider
from .metrics import (
    calculate_metrics,
    compute_drawdown_series,
    compute_benchmark_candles,
    compute_monthly_returns,
    compute_rolling_metrics,
    compute_top_drawdowns,
    compute_annual_returns,
    compute_monte_carlo,
    compute_return_distribution,
    compute_stress_periods,
)


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
    
    dd_series = compute_drawdown_series(equity_curve_dt)
    bench_candles = compute_benchmark_candles(
        data_provider, request.start_date, request.end_date, raw_result.bar_size, request.initial_capital
    )
    monthly_rets = compute_monthly_returns(equity_curve_dt)
    rolling = compute_rolling_metrics(equity_curve_dt, data_provider, raw_result.bar_size)
    top_dds = compute_top_drawdowns(equity_curve_dt)
    annual_rets = compute_annual_returns(equity_curve_dt)
    mc_raw = compute_monte_carlo(equity_curve_dt, raw_result.bar_size)
    ret_dist_raw = compute_return_distribution(equity_curve_dt)
    stress_raw = compute_stress_periods(equity_curve_dt, data_provider, raw_result.bar_size)

    # Assemble MonteCarloResult
    mc_result = MonteCarloResult(
        fan_chart=[MonteCarloFanPoint(**pt) for pt in mc_raw["fan_chart"]],
        terminal_wealth_bins=mc_raw["terminal_wealth_bins"],
        terminal_wealth_counts=mc_raw["terminal_wealth_counts"],
        sharpe_bins=mc_raw["sharpe_bins"],
        sharpe_counts=mc_raw["sharpe_counts"],
        max_dd_bins=mc_raw["max_dd_bins"],
        max_dd_counts=mc_raw["max_dd_counts"],
        calmar_bins=mc_raw["calmar_bins"],
        calmar_counts=mc_raw["calmar_counts"],
        prob_positive=mc_raw["prob_positive"],
        n_simulations=mc_raw["n_simulations"],
    ) if mc_raw["n_simulations"] > 0 else None

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
        drawdown_series=[DrawdownPoint(**pt) for pt in dd_series],
        benchmark_candles=[BenchmarkCandle(**pt) for pt in bench_candles],
        monthly_returns=[MonthlyReturn(**mr) for mr in monthly_rets],
        rolling_metrics=[RollingMetricPoint(**pt) for pt in rolling],
        top_drawdowns=[DrawdownEpisode(**ep) for ep in top_dds],
        annual_returns=[AnnualReturn(**ar) for ar in annual_rets],
        monte_carlo=mc_result,
        return_distribution=ReturnDistribution(**ret_dist_raw) if ret_dist_raw["bin_counts"] else None,
        stress_periods=[StressPeriodResult(**sp) for sp in stress_raw],
    )