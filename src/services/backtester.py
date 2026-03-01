import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
from hqg_algorithms import Strategy, Slice, PortfolioView, Cadence
from ..models.portfolio import Portfolio
from ..models.response import Trade
from ..services.data_provider.base_provider import BaseDataProvider
from ..execution.executor import RawExecutionResult


class Backtester:
    
    def __init__(self, data_provider: Optional[BaseDataProvider] = None):
        self.data_provider = data_provider
    
    # NOTE: this function currently fails, as RawExecutionResult now requires more fields
    # Do we need this? I like the idea of providing the option to clone the repo and just import a Backtester + run this function
    # async def run(self, strategy: Strategy, start_date: datetime, end_date: datetime, initial_capital: float = 10000.0) -> RawExecutionResult:
    #     """
    #     Run a backtest with the given strategy.

    #     Args:
    #         strategy: Strategy instance to backtest
    #         start_date: Start date for backtest
    #         end_date: End date for backtest
    #         initial_capital: Starting capital (default: 10000)

    #     Returns:
    #         RawExecutionResult with raw trades, equity curve, and final portfolio state.
    #         Metrics are computed separately after validation.
    #     """
    #     if self.data_provider is None:
    #         raise ValueError("data_provider required for run()")

    #     symbols = strategy.universe()
    #     cadence = strategy.cadence()
        
    #     data = self.data_provider.get_data(
    #         symbols=symbols,
    #         start_date=start_date,
    #         end_date=end_date,
    #         bar_size=cadence.bar_size
    #     )

    #     portfolio = Portfolio(
    #         initial_cash=initial_capital,
    #         symbols=symbols
    #     )

    #     trades, ohlc = self._run_loop(strategy, data, portfolio, cadence)

    #     final_prices = self._get_final_prices(data, symbols)

    #     return RawExecutionResult(
    #         trades=[t.model_dump() for t in trades],
    #         equity_curve={str(ts): value for ts, value in portfolio.equity_curve.items()},
    #         ohlc=ohlc,
    #         final_value=portfolio.get_total_value(final_prices),
    #         final_positions=portfolio.positions.copy(),
    #         final_cash=portfolio.cash
    #     )
    
    # TODO: add implementation for additional features: param / data noise, dropout, etc. 
    #async def run_advanced():
    #    pass

    
    # TODO duckdb?
    # NOTE: previous implementation is decide on bar close, execute on bar + exec_lag_bars close
    #   this does not work when cadence is > hourly
    # The other easy simplification is to assume immediate trading, which we do below.

    # NOTE: with yahoo finance, the order dates/times are not exact if weekly/monthly. Trading on Jan 1st means it traded on the close of the most recent trading day. our internal calc fixes this.
    def _run_loop(self, strategy: Strategy, slices: Dict, timestamps: list, portfolio: Portfolio) -> tuple[List[Trade], Dict]:
        """
        Core backtest loop.
        
        Args:
            strategy: Strategy instance
            slices: Pre-built dict of timestamp -> Slice
            timestamps: Ordered list of timestamps
            portfolio: Portfolio instance
        
        Returns:
            List of Trades
            Dict of portfolio OHLC
        """
        trades = []
        ohlc = []
        
        for i, timestamp in enumerate(timestamps):
            # Look up pre-built slice (O(1) dict access instead of pandas .loc)
            slice_obj = slices[timestamp]

            # update ohlc with current positions (before rebalancing)
            ohlc.append(portfolio.update_ohlc(timestamp, slice_obj))

            # make portfolio view
            prices = self._get_prices(slice_obj, strategy.universe())
            tv = portfolio.get_total_value(prices)
            portfolio.update_equity_curve(timestamp, tv)

            portfolio_view = PortfolioView(
                equity=tv,
                cash=portfolio.cash,
                positions=portfolio.positions,
                weights=portfolio.get_weights(prices, tv)
            )
            
            # get target weights
            target_weights = strategy.on_data(slice_obj, portfolio_view)
            
            # no rebalance if None
            if target_weights is None:
                continue
            
            # TODO (low priority): support usage of cadence.exec_lag_bars
            # TODO (low priority): support usage of cadence.call_phase

            exec_index = i      # assumes cadence.exec_lag_bars = DEFAULT (0)
            if exec_index >= len(timestamps):
                break
            
            exec_timestamp = timestamps[exec_index]
            exec_slice = slices[exec_timestamp]
            exec_prices = self._get_prices(exec_slice, strategy.universe())

            new_trades = portfolio.rebalance(
                target_weights,
                exec_prices,
                exec_timestamp
            )
            trades.extend(new_trades)
        
        # convert OHLC list to dict: timestamp -> {open, high, low, close}
        ohlc_dict = {}
        for entry in ohlc:
            ts = entry['timestamp']
            ohlc_dict[str(ts)] = {
                'open': entry['open'],
                'high': entry['high'],
                'low': entry['low'],
                'close': entry['close']
            }
        
        return trades, ohlc_dict

    def _get_prices(self, slice_obj: Slice, symbols: List[str]) -> Dict[str, float]:
        """Extract current prices from slice for given symbols."""
        prices = {}
        for symbol in symbols:
            price = slice_obj.close(symbol)
            if price is not None:
                prices[symbol] = price
        return prices

    # NOTE: not used (except by main loop, which is currently unsupported)
    # def _create_slice(self, timestamp_data: pd.Series) -> Slice:
    #     """Convert DataFrame row with MultiIndex columns to Slice dict format."""
    #     slice_data = {}
    #     for (symbol, field), value in timestamp_data.items():
    #         if symbol not in slice_data:
    #             slice_data[symbol] = {}
    #         slice_data[symbol][field] = value
    #     return Slice(slice_data)
        
    # def _get_final_prices(self, data: pd.DataFrame, symbols: List[str]) -> Dict[str, float]:
    #     """Get prices at the last timestamp."""
    #     final_timestamp = data.index[-1]
    #     timestamp_data = data.loc[final_timestamp]
    #     slice_obj = self._create_slice(timestamp_data)
    #     return self._get_prices(slice_obj, symbols)
