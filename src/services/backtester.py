import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
from hqg_algorithms import Strategy, Slice, PortfolioView, Cadence
from ..models.portfolio import Portfolio
from ..models.response import Trade
from ..services.data_provider.base_provider import BaseDataProvider
from ..services.data_provider.yf_provider import YFDataProvider
from ..validation.executor import RawExecutionResult


class Backtester:
    
    def __init__(self, data_provider: Optional[BaseDataProvider] = None):
        self.data_provider = data_provider or YFDataProvider()
    
    # TODO: add different types of fee structures (alpaca vs ibkr vs flat)
    async def run(self, strategy: Strategy, start_date: datetime, end_date: datetime, initial_capital: float = 10000.0) -> RawExecutionResult:
        """
        Run a backtest with the given strategy.

        Args:
            strategy: Strategy instance to backtest
            start_date: Start date for backtest
            end_date: End date for backtest
            initial_capital: Starting capital (default: 10000)

        Returns:
            RawExecutionResult with raw trades, equity curve, and final portfolio state.
            Metrics are computed separately after validation.
        """
        symbols = strategy.universe()
        cadence = strategy.cadence()

        data = self.data_provider.get_data(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            bar_size=cadence.bar_size
        )

        portfolio = Portfolio(
            initial_cash=initial_capital,
            symbols=symbols
        )

        trades, ohlc = self._run_loop(strategy, data, portfolio, cadence)

        final_prices = self._get_final_prices(data, symbols)

        return RawExecutionResult(
            trades=[t.model_dump() for t in trades],
            equity_curve={str(ts): value for ts, value in portfolio.equity_curve.items()},
            ohlc=ohlc,
            final_value=portfolio.get_total_value(final_prices),
            final_positions=portfolio.positions.copy(),
            final_cash=portfolio.cash
        )
    
    # TODO: add implementation for additional features: param / data noise, dropout, etc. 
    #async def run_advanced():
    #    pass

    
    # TODO duckdb?
    def _run_loop(self, strategy: Strategy, data: pd.DataFrame, portfolio: Portfolio, cadence: Cadence) -> tuple[List[Trade], Dict]:
        """
        Core backtest loop
        
        Returns:
            List of Trades
            DataFrame of portfolio OHLC
        """
        trades = []
        ohlc = []
        timestamps = data.index.unique()
        
        for i, timestamp in enumerate(timestamps):
            if i < cadence.exec_lag_bars:
                continue
            
            # create data slice at decision time
            timestamp_data = data.loc[timestamp]
            slice_obj = self._create_slice(timestamp_data)

            # update ohlc with current positions (before rebalancing)
            ohlc.append(portfolio.update_ohlc(timestamp, slice_obj))

            # make portfolio view
            prices = self._get_prices(slice_obj, strategy.universe())
            portfolio.update_equity_curve(timestamp, portfolio.get_total_value(prices))

            portfolio_view = PortfolioView(
                equity=portfolio.get_total_value(prices),
                cash=portfolio.cash,
                positions=portfolio.positions,
                weights=portfolio.get_weights(prices)
            )
            
            # get target weights
            target_weights = strategy.on_data(slice_obj, portfolio_view)
            
            # no rebalance if None
            if target_weights is None:
                continue
            
            # calculate execution timestamp with lag
            exec_index = i + cadence.exec_lag_bars
            if exec_index >= len(timestamps):
                break
            
            exec_timestamp = timestamps[exec_index]
            exec_slice = self._create_slice(data.loc[exec_timestamp])
            exec_prices = self._get_prices(exec_slice, strategy.universe())
            
            new_trades = portfolio.rebalance(
                target_weights,
                exec_prices,
                exec_timestamp
            )
            trades.extend(new_trades)
        
        # convert OHLC list to nested dict timestamp -> {open, high, low, close}
        ohlc_df = pd.DataFrame(ohlc)
        ohlc_dict = {}
        if not ohlc_df.empty:
            ohlc_df = ohlc_df.set_index('timestamp')
            for ts, row in ohlc_df.iterrows():
                ohlc_dict[str(ts)] = {
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close']
                }
        
        return trades, ohlc_dict
    
    def _create_slice(self, timestamp_data: pd.Series) -> Slice:
        """Convert DataFrame row with MultiIndex columns to Slice dict format."""
        slice_data = {}
        for (symbol, field), value in timestamp_data.items():
            if symbol not in slice_data:
                slice_data[symbol] = {}
            slice_data[symbol][field] = value
        return Slice(slice_data)
    
    def _get_prices(self, slice_obj: Slice, symbols: List[str]) -> Dict[str, float]:
        """Extract current prices from slice for given symbols."""
        prices = {}
        for symbol in symbols:
            price = slice_obj.close(symbol)
            if price is not None:
                prices[symbol] = price
        return prices
    
    def _get_final_prices(self, data: pd.DataFrame, symbols: List[str]) -> Dict[str, float]:
        """Get prices at the last timestamp."""
        final_timestamp = data.index[-1]
        timestamp_data = data.loc[final_timestamp]
        slice_obj = self._create_slice(timestamp_data)
        return self._get_prices(slice_obj, symbols)