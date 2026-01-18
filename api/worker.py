"""
Worker script for executing backtests in sandboxed Docker container.

This script runs INSIDE the Docker container and:
1. Reads strategy code from environment variable
2. Executes the backtest with pre-downloaded data
3. Outputs results as JSON to stdout
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtester.runner import run_backtest_engine
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_builtins
from hqg_algorithms import Strategy, Cadence
import numpy as np
import pandas as pd
import math


def get_safe_namespace():
    """Same safe namespace as main API."""
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
        'Strategy': Strategy,
        'Cadence': Cadence,
        '__builtins__': {
            **safe_builtins,
            '__import__': safe_import,
            '__metaclass__': type,
            '__name__': 'restricted_module',
        },
        'np': np,
        'numpy': np,
        'pd': pd,
        'pandas': pd,
        'json': json,
        'math': math,
        'datetime': datetime,
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
        'float': float,
        'int': int,
        'str': str,
        'bool': bool,
        'list': list,
        'dict': dict,
        'set': set,
        'tuple': tuple,
        'map': map,
        'filter': filter,
        'any': any,
        'all': all,
    }


def parse_strategy_safe(code, parameters=None):
    """Parse strategy code safely."""
    safe_namespace = get_safe_namespace()

    try:
        # Compile with restrictions
        bytecode = compile_restricted(code, '<user_strategy>', 'exec')

        # Execute
        exec(bytecode, safe_namespace)
    except SyntaxError as e:
        raise ValueError(f"Syntax error: {e}")
    except Exception as e:
        raise ValueError(f"Failed to compile strategy: {e}")

    # Find Strategy subclass
    strategy_class = None
    for name, obj in safe_namespace.items():
        if isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
            strategy_class = obj
            break

    if strategy_class is None:
        raise ValueError("No Strategy subclass found")

    # Wrap with params if provided
    if parameters:
        original_class = strategy_class

        class StrategyWithParams(original_class):
            def __init__(self):
                try:
                    super().__init__(params=parameters)
                except TypeError:
                    super().__init__()
                    self.params = parameters

        StrategyWithParams.__name__ = original_class.__name__
        strategy_class = StrategyWithParams

    return strategy_class


def main():
    """Main worker entry point."""
    try:
        # Read inputs from environment variables
        code = os.environ.get('STRATEGY_CODE')
        tickers = os.environ.get('TICKERS', '').split(',')
        start_date_str = os.environ.get('START_DATE')
        end_date_str = os.environ.get('END_DATE')
        initial_cash = float(os.environ.get('INITIAL_CASH', '100000'))
        commission_rate = float(os.environ.get('COMMISSION_RATE', '0.005'))
        parameters_str = os.environ.get('PARAMETERS', '{}')

        if not code:
            raise ValueError("STRATEGY_CODE environment variable not set")

        if not tickers or tickers == ['']:
            raise ValueError("TICKERS environment variable not set")

        # Parse dates
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

        # Parse parameters JSON
        parameters = json.loads(parameters_str) if parameters_str != '{}' else None

        # Parse strategy code
        strategy_class = parse_strategy_safe(code, parameters)

        # Run backtest (data must already exist in /data)
        results = run_backtest_engine(
            algorithm_class=strategy_class,
            universe=tickers,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            commission_rate=commission_rate,
        )

        # Output results as JSON to stdout
        # The parent process will capture this
        json.dump(results, sys.stdout, default=str)
        sys.exit(0)

    except Exception as e:
        # Output error as JSON
        error_result = {
            "error": str(e),
            "type": type(e).__name__
        }
        json.dump(error_result, sys.stdout)
        sys.exit(1)


if __name__ == "__main__":
    main()
