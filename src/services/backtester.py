from typing import List, Dict, Optional, Set
from hqg_algorithms import Strategy, Slice, PortfolioView, TargetWeights, Hold, Liquidate, ExecutionTiming, Bar
from ..models.execution import FeatureFlags
from ..models.portfolio import Portfolio
from ..models.response import Trade
from ..models.recorder import PortfolioRecorder
from ..services.data_provider.base_provider import BaseDataProvider

from enum import Enum
import random
import types
import sys

class Noise(Enum):
    # 1-indexed so there aren't issues with 0 being evaluated
    # as false in an if statement.
    UNIFORM = 1
    NORMAL = 2

class Backtester:
    
    def __init__(
        self,
        config_module = None,
        flags = None,
        data_provider: Optional[BaseDataProvider] = None,
    ) -> None:
        self.data_provider = data_provider
        if flags:
            self.flags = flags
        else:
            self.flags = set()

        # ADD_RANDOM_NOISE = 0,
        # SLIPPAGE = 1,
        # COMMISSION = 2,

        if config_module is not None:
            sys.modules['config'] = config_module


    # TODO: add implementation for additional features: param / data noise, dropout, etc. 
    #async def run_advanced():
    #    pass

    # TODO: add a new route + hqg-dash tab -- MC simulation

    
    def _run_loop(
        self,
        strategy: Strategy,
        slices: Dict,
        timestamps: list,
        portfolio: Portfolio,
        recorder: PortfolioRecorder,
    ) -> List[Trade]:
        """
        Core backtest loop.
        
        Args:
            strategy: Strategy instance
            slices: Pre-built dict of timestamp -> Slice
            timestamps: Ordered list of timestamps
            portfolio: Portfolio instance
            recorder: PortfolioRecorder for time-series accumulation
        
        Returns:
            List of Trades (recorder holds ohlc, equity, weights)
        """
        universe = strategy.universe
        execution = strategy.cadence.execution
        trades = []


        if (FeatureFlags.ADD_RANDOM_NOISE in self.flags):
            slices = self._layer_noise_on_market_data(timestamps, slices, universe, Noise.NORMAL)

        for i, timestamp in enumerate(timestamps):
            slice_obj = slices[timestamp]
            prices = self._get_close(slice_obj, universe)
            tv = portfolio.get_total_value(prices)

            # capture ohlc, equity, weights
            recorder.snapshot(
                timestamp=timestamp,
                cash=portfolio.cash,
                positions=portfolio.positions,
                slice_obj=slice_obj,
                prices=prices,
                total_value=tv,
            )

            portfolio_view = PortfolioView(
                equity=tv,
                cash=portfolio.cash,
                positions=portfolio.positions,
                weights=portfolio.get_weights(prices, tv)
            )


            # Adds noise to the current layer before it goes to the strategy
            if (FeatureFlags.SLIPPAGE in self.flags):
                 slice_obj = self._layer_noise_on_slice(slice_obj, universe, Noise.NORMAL)

            # determine target weights via Signal
            signal = strategy.on_data(slice_obj, portfolio_view)

            if isinstance(signal, Hold):
                continue
            if isinstance(signal, Liquidate):
                target_weights = {symbol: 0.0 for symbol in universe}
            elif isinstance(signal, TargetWeights):
                target_weights = dict(signal.weights)
            else:
                raise TypeError(f"on_data returned unknown signal type: {type(signal).__name__}")

            # determine execution prices via ExecutionTiming
            if execution == ExecutionTiming.CLOSE_TO_CLOSE:
                exec_prices = prices
                exec_timestamp = timestamp

            elif execution == ExecutionTiming.CLOSE_TO_NEXT_OPEN:
                if i + 1 >= len(timestamps):
                    break
                next_slice = slices[timestamps[i + 1]]
                exec_prices = self._get_open(next_slice, universe)
                exec_timestamp = timestamps[i + 1]

            else:
                raise ValueError(f"Unsupported ExecutionTiming: {execution}")

            new_trades = portfolio.rebalance(target_weights, exec_prices, exec_timestamp)
            trades.extend(new_trades)

        return trades


    def _get_close(self, slice_obj: Slice, symbols: List[str]) -> Dict[str, float]:
        """Extract current prices from slice for given symbols."""
        prices = {}
        for symbol in symbols:
            price = slice_obj.close(symbol)
            if price is not None:
                prices[symbol] = price
        return prices
    def _get_open(self, slice_obj: Slice, symbols: List[str]) -> Dict[str, float]:
        """Extract open prices from slice for given symbols."""
        prices = {}
        for symbol in symbols:
            price = slice_obj.open(symbol)
            if price is not None:
                prices[symbol] = price
        return prices
    
    def _get_high(self, slice_obj: Slice, symbols: List[str]) -> Dict[str, float]:
        """Extract open prices from slice for given symbols."""
        prices = {}
        for symbol in symbols:
            price = slice_obj.high(symbol)
            if price is not None:
                prices[symbol] = price
        return prices
    def _get_low(self, slice_obj: Slice, symbols: List[str]) -> Dict[str, float]:
        """Extract open prices from slice for given symbols."""
        prices = {}
        for symbol in symbols:
            price = slice_obj.low(symbol)
            if price is not None:
                prices[symbol] = price
        return prices
    def _get_volume(self, slice_obj: Slice, symbols: List[str]) -> Dict[str, float]:
        """Extract open prices from slice for given symbols."""
        prices = {}
        for symbol in symbols:
            price = slice_obj.volume(symbol)
            if price is not None:
                prices[symbol] = price
        return prices

    def _add_noise(self, prices: Dict[str, float], symbols: List[str], noise: Noise) -> Dict[str, float]:
        """ Returns new price data with noise added according to the input distribution. """
        new_prices = {}

        try:
            noise_range = sys.modules["config"].noise_range
        except:
            noise_range = 0.05

        for symbol in symbols:
            match (noise):
                case Noise.UNIFORM:
                    price = prices[symbol] + random.uniform(prices[symbol] - prices[symbol]*noise_range, prices[symbol] + prices[symbol]*noise_range)
                case Noise.NORMAL:
                    price = prices[symbol] + random.normalvariate(mu=prices[symbol], sigma=prices[symbol]*noise_range)

            new_prices[symbol] = price

            if price is None or price < 0:
                new_prices[symbol] = prices[symbol]

        return new_prices

    def _layer_noise_on_slice(self, slice_obj: Slice, universe: list, noise: Noise) -> Slice:
        """ Creates a new slice with the same price data + some noise as slice_obj """
        open = self._get_open(slice_obj, universe)
        high = self._get_high(slice_obj, universe)
        low = self._get_low(slice_obj, universe)
        close = self._get_close(slice_obj, universe)
        volume = self._get_volume(slice_obj, universe)

        open = self._add_noise(open, universe, noise)
        high =self._add_noise(high, universe, noise)
        low = self._add_noise(low, universe, noise)
        close = self._add_noise(close, universe, noise)
        volume = self._add_noise(volume, universe, noise)

        bars = {}
        for s in universe:
            bars[s] = Bar(
                open=open[s],
                high=high[s],
                low=low[s],
                close=close[s],
                volume=volume[s]
            )
        return Slice(bars)

    def _layer_noise_on_market_data(self, timestamps: list, slices: Dict, universe: list, noise: Noise) -> Dict:
        """ Computes new slices for every timestamp with noise"""
        new_slices = dict()

        for i, timestamp in enumerate(timestamps):
            slice_obj = slices[timestamp]
            new_slices[timestamp] = self._layer_noise_on_slice(slice_obj, universe, noise)

        return new_slices

    ###############################################################################

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
