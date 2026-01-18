"""
Helper functions for parsing user-submitted strategy code.
"""

import re
import math
import fcntl
from datetime import datetime
from typing import Any
from pathlib import Path
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_builtins
from hqg_algorithms import Strategy, Cadence
import numpy as np
import pandas as pd
import json


def parse_date_from_string(date_str: str | None, default: datetime) -> datetime:
    """
    Parse date string in YYYY-MM-DD format.
    Returns default if date_str is None or invalid.
    """
    if date_str is None:
        return default

    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return default


def extract_tickers_from_code(code: str) -> list[str]:
    """
    Extract ticker symbols from strategy code by parsing the universe() method.

    Looks for patterns like:
        def universe(self):
            return ['SPY', 'QQQ']

    Or:
        def universe(self):
            return ["AAPL", "MSFT", "GOOGL"]

    Returns:
        List of ticker symbols (uppercase). 

    Examples:
        >>> code = '''
        ... def universe(self):
        ...     return ['SPY', 'QQQ']
        ... '''
        >>> extract_tickers_from_code(code)
        ['SPY', 'QQQ']
    """
    # Pattern to match: def universe(self): ... return ['TICKER', 'TICKER']
    # Handles both single and double quotes, whitespace variations
    universe_pattern = r'def\s+universe\s*\([^)]*\)\s*:.*?return\s*\[(.*?)\]'

    match = re.search(universe_pattern, code, re.DOTALL)

    try: 
        return match.group(1)
    except:
        return []
        


def extract_class_name_from_code(code: str) -> str | None:
    """
    Extract the strategy class name from user code.

    Looks for patterns like:
        class MyStrategy(Strategy):

    Returns:
        Class name (e.g., 'MyStrategy') or None if not found.

    Examples:
        >>> code = "class MyStrategy(Strategy):\\n    pass"
        >>> extract_class_name_from_code(code)
        'MyStrategy'
    """
    # Pattern to match: class ClassName(Strategy):
    class_pattern = r'class\s+(\w+)\s*\(\s*Strategy\s*\)\s*:'

    match = re.search(class_pattern, code)

    if match:
        return match.group(1)

    return None


def validate_strategy_structure(code: str) -> tuple[bool, str | None]:
    """
    Validate that code has the basic structure of a Strategy class.

    Returns:
        (is_valid, error_message) - error_message is None if valid

    Examples:
        >>> code = "class MyStrategy(Strategy):\\n    def on_data(self, slice, portfolio):\\n        pass"
        >>> validate_strategy_structure(code)
        (True, None)
        >>> validate_strategy_structure("print('hello')")
        (False, 'No Strategy class found')
    """
    # Check for Strategy class
    if not re.search(r'class\s+\w+\s*\(\s*Strategy\s*\)\s*:', code):
        return False, "No Strategy class found (must subclass Strategy)"

    # Check for on_data method
    if not re.search(r'def\s+on_data\s*\(', code):
        return False, "No on_data method found (required for strategy execution)"

    return True, None


def validate_tickers(tickers: list[str]) -> tuple[list[str], str | None]:
    """Validate and normalize ticker symbols."""
    if not tickers or len(tickers) == 0:
        raise ValueError("At least one ticker is required")

    if len(tickers) > 50:
        raise ValueError("Too many tickers (max 50)")

    normalized = []
    for ticker in tickers:
        ticker = ticker.strip().upper()

        if not ticker or len(ticker) > 5 or not ticker.isalnum():
            raise ValueError(f"Invalid ticker format: {ticker}")

        normalized.append(ticker)

    # Remove duplicates while preserving order
    seen = set()
    unique_tickers = []
    for ticker in normalized:
        if ticker not in seen:
            seen.add(ticker)
            unique_tickers.append(ticker)

    return unique_tickers, None


def get_safe_namespace():
    """
    Returns a safe namespace with pre-approved libraries and functions.

    Allows:
    - numpy, pandas for data manipulation
    - Standard math operations
    - Custom class definitions (automatically allowed by RestrictedPython)
    - json for data parsing

    Blocks:
    - File I/O (open, file)
    - System calls (os.system, subprocess)
    - Arbitrary imports (__import__)
    - exec, eval, compile
    """
    def safe_import(name, *args, **kwargs):
        """Only allow importing pre-approved modules."""
        allowed_modules = {
            'hqg_algorithms': type('hqg_algorithms', (), {
                'Strategy': Strategy,
                'Cadence': Cadence,
            }),
            'numpy': np,
            'pandas': pd,
            'json': json,
            'math': math,
            'datetime': type('datetime', (), {'datetime': datetime}),
        }
        if name in allowed_modules:
            return allowed_modules[name]
        raise ImportError(f"Import of '{name}' is not allowed")

    return {
        # Core classes
        'Strategy': Strategy,
        'Cadence': Cadence,

        # Safe builtins with custom import and metaclass support
        '__builtins__': {
            **safe_builtins,
            '__import__': safe_import,
            '__metaclass__': type,
            '__name__': 'restricted_module',
        },

        # Pre-approved libraries (already imported, safe to expose)
        'np': np,
        'numpy': np,
        'pd': pd,
        'pandas': pd,
        'json': json,
        'math': math,

        # Date/time
        'datetime': datetime,

        # Math operations
        'abs': abs,
        'round': round,
        'len': len,
        'range': range,
        'enumerate': enumerate,
        'zip': zip,
        'min': min,
        'max': max,
        'sum': sum,
        'sorted': sorted,
        'reversed': reversed,

        # Type conversions
        'float': float,
        'int': int,
        'str': str,
        'bool': bool,
        'list': list,
        'dict': dict,
        'set': set,
        'tuple': tuple,

        # Functional
        'map': map,
        'filter': filter,
        'any': any,
        'all': all,
    }


def compile_safe_code(code: str):
    """
    Compile user code with RestrictedPython.

    Returns: (compiled_bytecode, safe_namespace)
    Raises: ValueError if code contains restricted operations
    """
    safe_namespace = get_safe_namespace()

    try:
        bytecode = compile_restricted(code, '<user_strategy>', 'exec')
        return bytecode, safe_namespace
    except SyntaxError as e:
        raise ValueError(f"Syntax error: {e}")
    except Exception as e:
        raise ValueError(f"An unexpected error occurred: {str(e)}")


def parse_strategy_code_safe(code: str, parameters: dict[str, Any] | None = None):
    """
    Safely parse and extract Strategy class from user code.

    Args:
        code: User-submitted strategy code
        parameters: Optional custom parameters to pass to strategy constructor

    Returns:
        Strategy class (not instance)

    Raises:
        ValueError: If code is invalid or no Strategy subclass found
    """
    # Compile safely
    bytecode, safe_namespace = compile_safe_code(code)

    # Execute in safe namespace
    exec(bytecode, safe_namespace)

    # Find Strategy subclass
    strategy_class = None
    for obj in safe_namespace.values():
        if isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
            strategy_class = obj
            break

    if strategy_class is None:
        raise ValueError("No Strategy subclass found in code")

    # If parameters provided, wrap to pass them to constructor
    if parameters:
        original_class = strategy_class

        class StrategyWithParams(original_class):
            def __init__(self):
                try:
                    # Try to pass parameters to parent constructor
                    super().__init__(params=parameters)
                except TypeError:
                    # If parent doesn't accept params, just call it normally
                    super().__init__()
                    # Store parameters as instance variable
                    self.params = parameters

        StrategyWithParams.__name__ = original_class.__name__
        strategy_class = StrategyWithParams

    return strategy_class


def download_data_with_lock(
    data_manager,
    lock_path: Path,
    symbols: list[str],
    start_date: datetime,
    end_date: datetime,
):
    """
    Download market data with file locking to prevent race conditions.

    This ensures only one process downloads data at a time, preventing
    file corruption when multiple users request the same ticker.

    Args:
        data_manager: DataManager instance
        lock_path: Path to lock file
        symbols: List of ticker symbols
        start_date: Start date for data
        end_date: End date for data
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_path, 'w') as f:
        # Acquire exclusive lock (blocks until available)
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

        try:
            data_manager.get_universe_data(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                auto_download=True
            )
        finally:
            # Release lock
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def format_results_for_frontend(
    results: dict,
    initial_cash: float,
    start_date: datetime,
) -> dict:
    """
    Format backtest results for frontend consumption.

    Args:
        results: Raw results from backtest engine
        initial_cash: Initial capital amount
        start_date: Backtest start date (used as fallback for timestamps)

    Returns:
        Formatted dict with equityCurve, orders, summary, and metrics
    """
    equity_curve = results.get('equity_curve', [])
    fills = results.get('fills', [])
    performance = results.get('performance_report', {})
    final_snapshot = results.get('final_snapshot', {})

    # Format equity curve for charting
    formatted_equity_curve = []
    for point in equity_curve:
        timestamp = point['time']
        if isinstance(timestamp, datetime):
            timestamp = int(timestamp.timestamp())
        equity = point['equity']
        formatted_equity_curve.append({
            "time": timestamp,
            "open": round(equity, 2),
            "high": round(equity * 1.001, 2),
            "low": round(equity * 0.999, 2),
            "close": round(equity, 2),
        })

    # Format orders/fills
    orders = []
    for i, fill in enumerate(fills):
        fill_time = fill.get('time') or fill.get('filled_at') or fill.get('submitted_at')
        if fill_time is None:
            timestamp_str = start_date.strftime("%b %d, %Y, %I:%M %p")
        elif isinstance(fill_time, datetime):
            timestamp_str = fill_time.strftime("%b %d, %Y, %I:%M %p")
        elif hasattr(fill_time, 'strftime'):
            timestamp_str = fill_time.strftime("%b %d, %Y, %I:%M %p")
        else:
            try:
                parsed = datetime.fromisoformat(str(fill_time).replace('Z', '+00:00'))
                timestamp_str = parsed.strftime("%b %d, %Y, %I:%M %p")
            except:
                timestamp_str = start_date.strftime("%b %d, %Y, %I:%M %p")

        quantity = fill.get('filled_qty') or fill.get('quantity', 0)
        direction = fill.get('direction', 'buy')
        is_buy = direction == 'buy' if isinstance(direction, str) else fill.get('is_buy', True)

        orders.append({
            "id": str(i + 1),
            "timestamp": timestamp_str,
            "ticker": fill.get('symbol', 'UNKNOWN'),
            "type": "Buy" if is_buy else "Sell",
            "price": round(fill.get('fill_price', 0), 2),
            "amount": int(quantity),
        })

    # Calculate summary metrics
    final_equity = final_snapshot.get('total_equity', initial_cash)
    net_profit = final_equity - initial_cash
    total_return_pct = (final_equity - initial_cash) / initial_cash
    total_volume = sum(o["price"] * o["amount"] for o in orders)
    fees = sum(fill.get('commission', 0) for fill in fills)

    summary = performance.get('summary', {})
    trade_metrics = performance.get('trade_metrics', {})
    risk_metrics = performance.get('risk_metrics', {})

    def to_python(val, default=0):
        """Convert numpy/pandas values to Python native types."""
        if val is None:
            return default
        if hasattr(val, 'item'):
            val = float(val.item())
        else:
            val = float(val)
        if math.isinf(val) or math.isnan(val):
            return default
        return val

    return {
        "summary": {
            "initialCash": float(initial_cash),
            "finalEquity": round(float(final_equity), 2),
            "totalReturn": round(float(total_return_pct) * 100, 2),
            "totalReturnPct": round(float(total_return_pct), 4),
            "numTrades": int(len(orders)),
            "netProfit": round(float(net_profit), 2),
            "fees": round(float(fees), 2),
            "volume": round(float(total_volume), 2),
        },
        "metrics": {
            "sharpeRatio": round(to_python(summary.get('sharpe_ratio', 0)), 2),
            "sortinoRatio": round(to_python(summary.get('sortino_ratio', 0)), 2),
            "alpha": round(to_python(risk_metrics.get('alpha', 0)), 2),
            "beta": round(to_python(risk_metrics.get('beta', 1), 1), 2),
            "maxDrawdown": round(abs(to_python(summary.get('max_drawdown', 0))) * 100, 2),
            "winRate": round(to_python(summary.get('win_rate', 0)) * 100, 2),
            "profitFactor": round(to_python(trade_metrics.get('profit_factor', 0)), 2),
            "psr": round(to_python(performance.get('psr', 0)), 2),
            "avgWinPct": round(to_python(trade_metrics.get('avg_win_pct', 0)) * 100, 2),
            "avgLossPct": round(abs(to_python(trade_metrics.get('avg_loss_pct', 0))) * 100, 2),
            "linearityError": round(to_python(performance.get('linearity_error', 0)), 2),
            "rateDrift": round(to_python(performance.get('rate_drift', 0)), 2),
            "volatility": round(to_python(summary.get('annualized_volatility', 0)), 4),
        },
        "equityCurve": formatted_equity_curve,
        "orders": orders,
    }