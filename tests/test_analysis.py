import pytest
from datetime import datetime

from src.validation.analysis import StaticAnalyzer, AnalysisError
from src.models.request import BacktestRequest
from tests.test_strategies.pytest_strategies import TestStrategies

def make_request(code: str) -> BacktestRequest:
    return BacktestRequest(
        strategy_code=code,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2021, 1, 1),
        initial_capital=10000.0,
    )

class TestValidStrategies:
    """Test that valid strategy code passes analysis."""

    def test_minimal_strategy(self):
        request = make_request(TestStrategies.VALID_MINIMAL)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, BacktestRequest), f"Expected BacktestRequest, got {type(result)}"
        assert result == request

    def test_numpy_pandas_strategy(self):
        request = make_request(TestStrategies.VALID_NUMPY_PANDAS)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, BacktestRequest)

    def test_math_strategy(self):
        request = make_request(TestStrategies.VALID_MATH)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, BacktestRequest)

    def test_comprehensions_strategy(self):
        request = make_request(TestStrategies.VALID_COMPREHENSIONS)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, BacktestRequest)

class TestSyntaxErrors:
    def test_invalid_syntax(self):
        """Syntax errors should be caught."""
        request = make_request(TestStrategies.MALICIOUS_SYNTAX_ERROR)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)
        assert not result.is_empty()
        assert any("Syntax error" in e for e in result.errors)

    def test_syntax_error_location(self):
        request = make_request(TestStrategies.MALICIOUS_SYNTAX_ERROR)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)
        assert any("line" in e for e in result.errors)

class TestForbiddenImports:
    @pytest.mark.parametrize("code,module", [
        (TestStrategies.MALICIOUS_OS_IMPORT, "os"),
        (TestStrategies.MALICIOUS_SUBPROCESS_IMPORT, "subprocess"),
        (TestStrategies.MALICIOUS_SOCKET_IMPORT, "socket"),
        (TestStrategies.MALICIOUS_REQUESTS_IMPORT, "requests"),
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

class TestForbiddenBuiltins:
    """Test that forbidden builtin calls are rejected."""

    @pytest.mark.parametrize("code,builtin", [
        (TestStrategies.MALICIOUS_EVAL, "eval"),
        (TestStrategies.MALICIOUS_EXEC, "exec"),
        (TestStrategies.MALICIOUS_OPEN_FILE, "open"),
        (TestStrategies.MALICIOUS_COMPILE, "compile"),
        (TestStrategies.MALICIOUS_DUNDER_IMPORT, "__import__"),
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

class TestForbiddenAttributes:
    """Test that forbidden attribute access is rejected."""

    @pytest.mark.parametrize("code,attr", [
        (TestStrategies.MALICIOUS_GLOBALS_ACCESS, "__globals__"),
        (TestStrategies.MALICIOUS_CODE_ACCESS, "__code__"),
        (TestStrategies.MALICIOUS_CLASS_ESCAPE, "__class__"),
        (TestStrategies.MALICIOUS_MRO_ACCESS, "__mro__"),
    ])
    def test_forbidden_attribute(self, code: str, attr: str):
        request = make_request(code)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError), f"Access to {attr} should be rejected"
        assert not result.is_empty()
        assert any(attr in e and "forbidden" in e for e in result.errors)

    def test_bases_forbidden(self):
        request = make_request(TestStrategies.MALICIOUS_BUILTINS_VIA_CLASS)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)
        assert any("__bases__" in e or "__class__" in e for e in result.errors)

class TestMissingStrategy:
    def test_no_strategy_class(self):
        request = make_request(TestStrategies.MALICIOUS_NO_STRATEGY)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)
        assert any("Strategy" in e for e in result.errors)

    def test_wrong_inheritance(self):
        request = make_request(TestStrategies.MALICIOUS_WRONG_INHERITANCE)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)
        assert any("Strategy" in e for e in result.errors)

    def test_strategy_no_inherit(self):
        request = make_request(TestStrategies.MALICIOUS_FAKE_STRATEGY_CLASS)
        result = StaticAnalyzer.analyze(request)

        assert isinstance(result, AnalysisError)
        assert any("Strategy" in e for e in result.errors)

VALID_STRATEGIES = [
    ("minimal", TestStrategies.VALID_MINIMAL),
    ("numpy_pandas", TestStrategies.VALID_NUMPY_PANDAS),
    ("math", TestStrategies.VALID_MATH),
    ("comprehensions", TestStrategies.VALID_COMPREHENSIONS),
]

INVALID_STRATEGIES = [
    ("syntax", TestStrategies.MALICIOUS_SYNTAX_ERROR),
    ("import_os", TestStrategies.MALICIOUS_OS_IMPORT),
    ("import_subprocess", TestStrategies.MALICIOUS_SUBPROCESS_IMPORT),
    ("import_socket", TestStrategies.MALICIOUS_SOCKET_IMPORT),
    ("import_requests", TestStrategies.MALICIOUS_REQUESTS_IMPORT),
    ("builtin_eval", TestStrategies.MALICIOUS_EVAL),
    ("builtin_exec", TestStrategies.MALICIOUS_EXEC),
    ("builtin_open", TestStrategies.MALICIOUS_OPEN_FILE),
    ("builtin_compile", TestStrategies.MALICIOUS_COMPILE),
    ("builtin_import", TestStrategies.MALICIOUS_DUNDER_IMPORT),
    ("attr_globals", TestStrategies.MALICIOUS_GLOBALS_ACCESS),
    ("attr_code", TestStrategies.MALICIOUS_CODE_ACCESS),
    ("attr_builtins", TestStrategies.MALICIOUS_BUILTINS_VIA_CLASS),
    ("attr_class", TestStrategies.MALICIOUS_CLASS_ESCAPE),
    ("attr_mro", TestStrategies.MALICIOUS_MRO_ACCESS),
    ("no_strategy", TestStrategies.MALICIOUS_NO_STRATEGY),
    ("wrong_inheritance", TestStrategies.MALICIOUS_WRONG_INHERITANCE),
    ("no_inherit", TestStrategies.MALICIOUS_FAKE_STRATEGY_CLASS),
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
