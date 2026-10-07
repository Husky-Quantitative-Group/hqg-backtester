import asyncio
import logging
import pandas as pd
from datetime import datetime
from typing import Dict, Any
from hqg_algorithms import extract_metadata

from ..models.request import BacktestRequest, ValidationException, ExecutionException
from ..services.data_provider.datafeed_provider_alt import DataFeedAltProvider
from ..services.data_provider.datafeed_provider_securities import DataFeedSecuritiesProvider
from .executor import Executor, ExecutionPayload, RawExecutionResult
from .output_validator import OutputValidator
from .analysis import StaticAnalyzer

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Validation pipeline orchestrator.

    Flow:
        BacktestRequest
        → parse strategy (extract universe, dates, cadence)
        → fetch market data (hqg-datafeed)
        → fetch alt data (hqg-datafeed)
        → convert data → JSON
        → build ExecutionPayload
        → Executor (Docker container)
        → OutputValidator (sanity checks)
        → RawExecutionResult (ready for metrics)
    """

    _semaphore = asyncio.Semaphore(13)  # 13 maximum backtests at a time (one for each member)

    def __init__(self):
        self.securities_provider = DataFeedSecuritiesProvider()
        self.alt_provider = DataFeedAltProvider()
        self.executor = Executor()
        self.output_validator = OutputValidator()

    async def run(self, request: BacktestRequest) -> RawExecutionResult:
        """
        Run the full validation pipeline.

        Returns validated RawExecutionResult ready for metrics computation.
        """
        async with self._semaphore:
            try:
                # Analyze Code
                StaticAnalyzer.analyze(request)
                if not request.errors.is_empty():
                    raise ValidationException(request.errors)
 
                # Parse strategy code to extract universe + cadence
                strategy_metadata = extract_metadata(request.strategy_code)
                universe, cadence = strategy_metadata.universe, strategy_metadata.cadence
                alt_data = strategy_metadata.alt_data

                logger.info(
                    f"Parsed strategy: universe={universe}, "
                    f"alt_data={alt_data}, bar_size={cadence.bar_size}"
                )
            except ValueError as e:
                request.errors.add(str(e))
                raise ValidationException(request.errors)
            try:
                # Securities Data Requests
                data = await asyncio.to_thread(
                    self.securities_provider.get_data,
                    symbols=universe,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    bar_size=cadence.bar_size,
                )
                # edge case
                if data.empty:
                    request.errors.add("No market data available for the specified date range and universe")
                    raise ExecutionException(request.errors)
                logger.info(f"Fetched {len(data)} bars for {universe}")

                # Convert DataFrame → JSON for container
                # TODO: Use Arrow IPC instead of JSON for faster serialization?
                market_data_json = dataframe_to_json(data, universe)

                # Alt Data Requests
                alt_data_json: Dict[str, Any] = {}

                if alt_data:
                    alt_frames = await asyncio.to_thread(
                        self.alt_provider.get_data,
                        series=alt_data,
                        start_date=request.start_date,
                        end_date=request.end_date,
                    )
                    alt_data_json = alt_dataframe_to_json(alt_frames, alt_data)

                # Build execution payload
                payload = ExecutionPayload(
                    strategy_code=request.strategy_code,
                    name=request.name,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    initial_capital=request.initial_capital,
                    market_data=market_data_json,
                    alt_data=alt_data_json,
                    bar_size=cadence.bar_size,
                    config_params=request.config_params,
                )
                
                # Execute our payload
                raw_result = await asyncio.to_thread(self.executor.execute, payload)
                
                if not raw_result.errors.is_empty():
                    raise ExecutionException(raw_result.errors)

                # Validate output
                validated_result = self.output_validator.validate(raw_result)

                logger.info(f"Pipeline complete. Final value: {validated_result.final_value}")
                return validated_result
            except ValueError as e:
                request.errors.add(str(e))
                raise ExecutionException(request.errors)

def dataframe_to_json(data: pd.DataFrame, symbols: list[str]) -> Dict[str, Any]:
    """
    Convert MultiIndex DataFrame to JSON format expected by container.

    Input:  DataFrame with MultiIndex columns (symbol, field) and DatetimeIndex
    Output: {"AAPL": {"date": [...], "open": [...], "high": [...], ...}}
    """
    market_data = {}

    for symbol in symbols:
        symbol_data: Dict[str, list] = {"date": []}

        for field in ["open", "high", "low", "close", "volume"]:
            if (symbol, field) in data.columns:
                symbol_data[field] = data[(symbol, field)].tolist()

        # dates from index
        symbol_data["date"] = [ts.isoformat() for ts in data.index]

        market_data[symbol] = symbol_data

    return market_data


def alt_dataframe_to_json(data: dict[str, pd.DataFrame], series_ids: list[str]) -> Dict[str, Any]:
    """
    Convert raw alternative data to JSON for the execution payload.

    Input:  Dict of per-series DataFrames keyed by full series id. Each frame
            has a DatetimeIndex that may contain duplicates for revised series.
    Output: {"FRED.GDP": {"date": [...], "value": [...], "available_at": [...]}}
    """
    alt_data: Dict[str, Any] = {}

    if not data:
        return {series_id: {"date": []} for series_id in series_ids}

    for series_id in series_ids:
        frame = data.get(series_id)
        if frame is None:
            alt_data[series_id] = {"date": []}
            continue

        series_data: Dict[str, list] = {
            "date": [None if pd.isna(ts) else ts.isoformat() for ts in frame.index]
        }
        for field in frame.columns:
            series_data[str(field)] = [
                None if pd.isna(v) else (v.isoformat() if hasattr(v, "isoformat") else v)
                for v in frame[field]
            ]
        alt_data[series_id] = series_data

    return alt_data
