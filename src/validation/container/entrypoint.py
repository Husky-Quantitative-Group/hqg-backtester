#!/usr/bin/env python3
import sys
import time
import pandas as pd
from datetime import datetime
from uuid import uuid4
from enum import Enum
from typing import Dict, List, Any
from ...models.execution import ExecutionPayload, RawExecutionResult

from src.models.request import BacktestRequestError


# ── Portfolio class (copied from src/models/portfolio.py) ──

class OrderType(str, Enum):
    SELL = "Sell"
    BUY = "Buy"


class Trade:
    def __init__(self, id: str, timestamp: datetime, symbol: str, action: OrderType, shares: float, price: float):
        self.id = id
        self.timestamp = timestamp
        self.symbol = symbol
        self.action = action
        self.shares = shares
        self.price = price

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "ticker": self.symbol,
            "type": self.action.value,
            "amount": self.shares,
            "price": self.price,
        }


class Portfolio:
    def __init__(self, initial_cash: float, symbols: List[str]):
        self.cash = initial_cash
        self.positions: Dict[str, float] = {symbol: 0.0 for symbol in symbols}
        self.equity_curve: Dict[datetime, float] = {}

    def update_equity_curve(self, timestamp: datetime, total_value: float) -> None:
        self.equity_curve[timestamp] = total_value

    def get_total_value(self, prices: Dict[str, float]) -> float:
        positions_value = sum(
            self.positions.get(symbol, 0) * prices.get(symbol, 0)
            for symbol in self.positions
        )
        return self.cash + positions_value

    def get_weights(self, prices: Dict[str, float]) -> Dict[str, float]:
        wts = {}
        tv = self.get_total_value(prices)
        for tick, quantity in self.positions.items():
            if tick not in prices:
                continue
            wt = prices[tick] * quantity / tv
            wts[tick] = wt
        return wts

    def rebalance(self, target_weights: Dict[str, float], prices: Dict[str, float], timestamp: datetime) -> List[Trade]:
        trades = []

        total_weight = sum(target_weights.values())
        if total_weight > 1.0001:
            raise ValueError(f"Target weights sum to {total_weight}, must be <= 1.0")

        total_value = self.get_total_value(prices)

        target_positions = {}
        for symbol, weight in target_weights.items():
            if symbol not in prices:
                raise ValueError(f"No price available for {symbol}")

            target_value = total_value * weight
            target_shares = target_value / prices[symbol]
            target_positions[symbol] = target_shares

        for symbol in self.positions:
            current_shares = self.positions[symbol]
            target_shares = target_positions.get(symbol, 0.0)

            shares_to_trade = target_shares - current_shares

            if abs(shares_to_trade * prices.get(symbol, 0)) < 1:
                continue

            if symbol not in prices:
                continue

            price = prices[symbol]
            trade_value = abs(shares_to_trade) * price

            if shares_to_trade > 0:
                self.positions[symbol] += shares_to_trade
                self.cash -= trade_value

                trades.append(Trade(
                    id=str(uuid4()),
                    timestamp=timestamp,
                    symbol=symbol,
                    action=OrderType.BUY,
                    shares=shares_to_trade,
                    price=price,
                ))

            elif shares_to_trade < 0:
                shares_to_sell = abs(shares_to_trade)

                self.positions[symbol] -= shares_to_sell
                self.cash += trade_value

                trades.append(Trade(
                    id=str(uuid4()),
                    timestamp=timestamp,
                    symbol=symbol,
                    action=OrderType.SELL,
                    shares=shares_to_sell,
                    price=price,
                ))

        return trades

    def update_ohlc(self, timestamp: datetime, prices_dict: Dict[str, Dict[str, float]]) -> Dict:
        portfolio_open = self.cash
        portfolio_high = self.cash
        portfolio_low = self.cash
        portfolio_close = self.cash

        for symbol, shares in self.positions.items():
            if shares <= 0:
                continue

            if symbol not in prices_dict:
                continue

            open_price = prices_dict[symbol].get("open")
            high_price = prices_dict[symbol].get("high")
            low_price = prices_dict[symbol].get("low")
            close_price = prices_dict[symbol].get("close")

            if open_price is not None:
                portfolio_open += shares * open_price
            if high_price is not None:
                portfolio_high += shares * high_price
            if low_price is not None:
                portfolio_low += shares * low_price
            if close_price is not None:
                portfolio_close += shares * close_price

        return {
            'timestamp': timestamp,
            'open': portfolio_open,
            'high': portfolio_high,
            'low': portfolio_low,
            'close': portfolio_close
        }


def main():
    try:
        json_payload = sys.stdin.read()
        payload = ExecutionPayload.model_validate_json(json_payload)

        start = time.time()
        result_dict = execute_backtest(payload)
        result_dict["execution_time"] = time.time() - start

        result = RawExecutionResult(**result_dict)
        sys.stdout.write(result.model_dump_json())
        sys.exit(0)

    except Exception as e:
        errors = BacktestRequestError()
        errors.add(str(e))
        error_result = RawExecutionResult(
            trades=[],
            equity_curve={},
            ohlc={},
            final_value=0.0,
            final_cash=0.0,
            final_positions={},
            execution_time=0.0,
            errors=errors
        )
        sys.stdout.write(error_result.model_dump_json())
        sys.exit(1)


def execute_backtest(payload: ExecutionPayload) -> Dict[str, Any]:
    """
    Execute the backtest by running the strategy code with market data.

    Market data format (JSON):
    {
      "AAPL": {
        "date": ["2023-01-01", "2023-01-02"],
        "open": [149, 151],
        "high": [151, 153],
        "low": [148, 150],
        "close": [150, 152],
        "volume": [1000, 1100]
      },
      "TSLA": { ... }
    }
    """
    errors = BacktestRequestError()

    try:
        # Convert market_data JSON to pandas DataFrame (MultiIndex format)
        data = json_to_dataframe(payload.market_data)

        # Load strategy class
        strategy_namespace = {}
        exec(payload.strategy_code, strategy_namespace)

        # Find Strategy subclass
        from hqg_algorithms import Strategy
        strategy_class = None
        for name, obj in strategy_namespace.items():
            if isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
                strategy_class = obj
                break

        if strategy_class is None:
            raise ValueError("No Strategy subclass found in strategy_code")

        strategy = strategy_class()

        # Initialize portfolio
        symbols = strategy.universe()
        portfolio = Portfolio(initial_cash=payload.initial_capital, symbols=symbols)

        # Run backtest loop
        cadence = strategy.cadence()
        trades, ohlc = run_loop(strategy, data, portfolio, cadence)

        # Get final prices
        final_prices = get_final_prices(data, symbols)

        return {
            "trades": [t.to_dict() for t in trades],
            "equity_curve": {ts.isoformat(): value for ts, value in portfolio.equity_curve.items()},
            "ohlc": ohlc,
            "final_value": portfolio.get_total_value(final_prices),
            "final_cash": portfolio.cash,
            "final_positions": portfolio.positions.copy(),
            "errors": errors
        }

    except Exception as e:
        errors.add(f"Strategy execution error: {str(e)}")
        return {
            "trades": [],
            "equity_curve": {},
            "ohlc": {},
            "final_value": 0.0,
            "final_cash": 0.0,
            "final_positions": {},
            "errors": errors
        }


def json_to_dataframe(market_data: Dict[str, Any]) -> pd.DataFrame:
    """
    Convert JSON market data to pandas DataFrame with MultiIndex columns.

    Input: {"AAPL": {"date": [...], "open": [...], ...}}
    Output: DataFrame with DatetimeIndex and MultiIndex columns (symbol, field)
    """
    frames = {}
    for symbol, data_dict in market_data.items():
        df = pd.DataFrame(data_dict)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        frames[symbol] = df

    # Build MultiIndex DataFrame
    all_data = []
    for symbol, df in frames.items():
        for field in ["open", "high", "low", "close", "volume"]:
            if field in df.columns:
                all_data.append((symbol, field, df[field]))

    if not all_data:
        return pd.DataFrame()

    # Create MultiIndex columns
    tuples = [(symbol, field) for symbol, field, _ in all_data]
    columns = pd.MultiIndex.from_tuples(tuples)

    # Create DataFrame with MultiIndex columns
    formatted = pd.DataFrame({i: data for i, (_, _, data) in enumerate(all_data)})
    formatted.columns = columns

    return formatted


def run_loop(strategy, data: pd.DataFrame, portfolio: Portfolio, cadence) -> tuple:
    """Core backtest loop (copied from backtester.py)"""
    from hqg_algorithms import PortfolioView

    trades = []
    ohlc = []
    timestamps = data.index.unique()

    for i, timestamp in enumerate(timestamps):
        if i < cadence.exec_lag_bars:
            continue

        # Handle both Series and DataFrame from .loc
        timestamp_data = data.loc[timestamp]
        if isinstance(timestamp_data, pd.DataFrame):
            timestamp_data = timestamp_data.iloc[0]

        slice_obj = create_slice(timestamp_data)

        # Update portfolio OHLC
        prices_dict = slice_to_dict(slice_obj, strategy.universe())
        ohlc.append(portfolio.update_ohlc(timestamp, prices_dict))

        # Update equity curve
        prices = get_prices(slice_obj, strategy.universe())
        portfolio.update_equity_curve(timestamp, portfolio.get_total_value(prices))

        # Create portfolio view
        portfolio_view = PortfolioView(
            equity=portfolio.get_total_value(prices),
            cash=portfolio.cash,
            positions=portfolio.positions,
            weights=portfolio.get_weights(prices)
        )

        # Get target weights
        target_weights = strategy.on_data(slice_obj, portfolio_view)

        if target_weights is None:
            continue

        # Calculate execution timestamp with lag
        exec_index = i + cadence.exec_lag_bars
        if exec_index >= len(timestamps):
            break

        exec_timestamp = timestamps[exec_index]
        exec_data = data.loc[exec_timestamp]
        if isinstance(exec_data, pd.DataFrame):
            exec_data = exec_data.iloc[0]

        exec_slice = create_slice(exec_data)
        exec_prices = get_prices(exec_slice, strategy.universe())

        new_trades = portfolio.rebalance(target_weights, exec_prices, exec_timestamp)
        trades.extend(new_trades)

    # Convert OHLC list to nested dict
    ohlc_df = pd.DataFrame(ohlc)
    ohlc_dict = {}
    if not ohlc_df.empty:
        ohlc_df = ohlc_df.set_index('timestamp')
        for ts, row in ohlc_df.iterrows():
            if isinstance(ts, datetime):
                ohlc_dict[ts.isoformat()] = {
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close']
                }

    return trades, ohlc_dict


def create_slice(timestamp_data: pd.Series):
    """Convert DataFrame row to Slice dict format"""
    from hqg_algorithms import Slice
    slice_data = {}
    for (symbol, field), value in timestamp_data.items():
        if symbol not in slice_data:
            slice_data[symbol] = {}
        slice_data[symbol][field] = value
    return Slice(slice_data)


def slice_to_dict(slice_obj, symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """Convert Slice to dict for OHLC calculation"""
    prices_dict = {}
    for symbol in symbols:
        prices_dict[symbol] = {
            "open": slice_obj[symbol].get("open"),
            "high": slice_obj[symbol].get("high"),
            "low": slice_obj[symbol].get("low"),
            "close": slice_obj[symbol].get("close"),
        }
    return prices_dict


def get_prices(slice_obj, symbols: List[str]) -> Dict[str, float]:
    """Extract close prices from slice"""
    prices = {}
    for symbol in symbols:
        price = slice_obj.close(symbol)
        if price is not None:
            prices[symbol] = price
    return prices


def get_final_prices(data: pd.DataFrame, symbols: List[str]) -> Dict[str, float]:
    """Get prices at the last timestamp"""
    final_timestamp = data.index[-1]
    timestamp_data = data.loc[final_timestamp]
    slice_obj = create_slice(timestamp_data)
    return get_prices(slice_obj, symbols)


if __name__ == "__main__":
    main()
