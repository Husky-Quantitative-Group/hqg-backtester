"""test_parse_metadata.py — verify AST extraction handles all cases."""

import pytest
from src.utils.strategy_metadata import extract_metadata


# ── Valid strategies ─────────────────────────────────────────────────

class TestValidStrategies:
    def test_full_definition(self):
        meta = extract_metadata("""
from hqg_algorithms import Strategy, Cadence, BarSize, ExecutionTiming

class MyStrategy(Strategy):
    universe = ["SPY", "IEF", "GLD"]
    cadence = Cadence(bar_size=BarSize.WEEKLY, execution=ExecutionTiming.CLOSE_TO_NEXT_OPEN)

    def on_data(self, data, portfolio):
        pass
""")
        assert meta.universe == ["SPY", "IEF", "GLD"]
        assert meta.cadence.bar_size.value == "1w"
        assert meta.cadence.execution.value == "close_to_next_open"

    def test_cadence_omitted_uses_defaults(self):
        meta = extract_metadata("""
class MyStrategy(Strategy):
    universe = ["AAPL"]

    def on_data(self, data, portfolio):
        pass
""")
        assert meta.universe == ["AAPL"]
        assert meta.cadence.bar_size.value == "1d"
        assert meta.cadence.execution.value == "close_to_close"

    def test_cadence_partial_bar_size_only(self):
        meta = extract_metadata("""
class MyStrategy(Strategy):
    universe = ["BTC-USD"]
    cadence = Cadence(bar_size=BarSize.MONTHLY)

    def on_data(self, data, portfolio):
        pass
""")
        assert meta.cadence.bar_size.value == "1m"
        assert meta.cadence.execution.value == "close_to_close"

    def test_cadence_partial_execution_only(self):
        meta = extract_metadata("""
class MyStrategy(Strategy):
    universe = ["SPY"]
    cadence = Cadence(execution=ExecutionTiming.OPEN_TO_OPEN)

    def on_data(self, data, portfolio):
        pass
""")
        assert meta.cadence.bar_size.value == "1d"
        assert meta.cadence.execution.value == "open_to_open"

    def test_cadence_no_args_uses_defaults(self):
        meta = extract_metadata("""
class MyStrategy(Strategy):
    universe = ["SPY"]
    cadence = Cadence()

    def on_data(self, data, portfolio):
        pass
""")
        assert meta.cadence.bar_size.value == "1d"
        assert meta.cadence.execution.value == "close_to_close"

    def test_single_ticker(self):
        meta = extract_metadata("""
class MyStrategy(Strategy):
    universe = ["AAPL"]

    def on_data(self, data, portfolio):
        pass
""")
        assert meta.universe == ["AAPL"]

    def test_many_tickers(self):
        meta = extract_metadata("""
class MyStrategy(Strategy):
    universe = ["AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "NVDA", "BRK-B"]

    def on_data(self, data, portfolio):
        pass
""")
        assert len(meta.universe) == 8

    def test_extra_class_attributes_ignored(self):
        meta = extract_metadata("""
class MyStrategy(Strategy):
    universe = ["SPY"]
    cadence = Cadence(bar_size=BarSize.DAILY)
    some_param = 42
    name = "my strat"

    def on_data(self, data, portfolio):
        pass
""")
        assert meta.universe == ["SPY"]


# ── No strategy class found ─────────────────────────────────────────

class TestNoStrategyFound:
    def test_empty_source(self):
        with pytest.raises(ValueError, match="No strategy class"):
            extract_metadata("")

    def test_no_class(self):
        with pytest.raises(ValueError, match="No strategy class"):
            extract_metadata("x = 1\ny = 2\n")

    def test_class_without_universe(self):
        with pytest.raises(ValueError, match="No strategy class"):
            extract_metadata("""
class NotAStrategy(Strategy):
    cadence = Cadence()

    def on_data(self, data, portfolio):
        pass
""")


# ── Syntax error ─────────────────────────────────────────────────────

class TestSyntaxError:
    def test_invalid_python(self):
        with pytest.raises(ValueError, match="syntax error"):
            extract_metadata("def foo(:")


# ── Bad universe ─────────────────────────────────────────────────────

class TestBadUniverse:
    def test_universe_is_string(self):
        with pytest.raises(ValueError, match="list of strings"):
            extract_metadata("""
class MyStrategy(Strategy):
    universe = "AAPL"

    def on_data(self, data, portfolio):
        pass
""")

    def test_universe_is_int(self):
        with pytest.raises(ValueError, match="list of strings"):
            extract_metadata("""
class MyStrategy(Strategy):
    universe = 42

    def on_data(self, data, portfolio):
        pass
""")

    def test_universe_has_non_string_elements(self):
        with pytest.raises(ValueError, match="list of strings"):
            extract_metadata("""
class MyStrategy(Strategy):
    universe = ["AAPL", 123]

    def on_data(self, data, portfolio):
        pass
""")

    def test_universe_empty(self):
        with pytest.raises(ValueError, match="must not be empty"):
            extract_metadata("""
class MyStrategy(Strategy):
    universe = []

    def on_data(self, data, portfolio):
        pass
""")

    def test_universe_is_function_call(self):
        with pytest.raises(ValueError, match="list literal"):
            extract_metadata("""
class MyStrategy(Strategy):
    universe = get_sp500()

    def on_data(self, data, portfolio):
        pass
""")

    def test_universe_is_variable_reference(self):
        with pytest.raises(ValueError, match="list literal"):
            extract_metadata("""
TICKERS = ["AAPL"]

class MyStrategy(Strategy):
    universe = TICKERS

    def on_data(self, data, portfolio):
        pass
""")

    def test_universe_is_concatenation(self):
        with pytest.raises(ValueError, match="list literal"):
            extract_metadata("""
class MyStrategy(Strategy):
    universe = ["AAPL"] + ["MSFT"]

    def on_data(self, data, portfolio):
        pass
""")


# ── Bad cadence ──────────────────────────────────────────────────────

class TestBadCadence:
    def test_cadence_is_string(self):
        with pytest.raises(ValueError, match="Cadence\\(\\.\\.\\.\\) call"):
            extract_metadata("""
class MyStrategy(Strategy):
    universe = ["SPY"]
    cadence = "1d"

    def on_data(self, data, portfolio):
        pass
""")

    def test_cadence_is_dict(self):
        with pytest.raises(ValueError, match="Cadence\\(\\.\\.\\.\\) call"):
            extract_metadata("""
class MyStrategy(Strategy):
    universe = ["SPY"]
    cadence = {"bar_size": "1d"}

    def on_data(self, data, portfolio):
        pass
""")

    def test_cadence_wrong_function_name(self):
        with pytest.raises(ValueError, match="Cadence\\(\\.\\.\\.\\) call"):
            extract_metadata("""
class MyStrategy(Strategy):
    universe = ["SPY"]
    cadence = NotCadence(bar_size=BarSize.DAILY)

    def on_data(self, data, portfolio):
        pass
""")

    def test_cadence_invalid_bar_size(self):
        with pytest.raises(ValueError, match="unknown bar_size"):
            extract_metadata("""
class MyStrategy(Strategy):
    universe = ["SPY"]
    cadence = Cadence(bar_size=BarSize.HOURLY)

    def on_data(self, data, portfolio):
        pass
""")

    def test_cadence_invalid_execution(self):
        with pytest.raises(ValueError, match="unknown execution"):
            extract_metadata("""
class MyStrategy(Strategy):
    universe = ["SPY"]
    cadence = Cadence(execution=ExecutionTiming.FAKE)

    def on_data(self, data, portfolio):
        pass
""")

    def test_cadence_bar_size_is_variable(self):
        with pytest.raises(ValueError, match="must be BarSize.X"):
            extract_metadata("""
class MyStrategy(Strategy):
    universe = ["SPY"]
    cadence = Cadence(bar_size=my_var)

    def on_data(self, data, portfolio):
        pass
""")

    def test_cadence_bar_size_is_string_literal(self):
        with pytest.raises(ValueError, match="must be BarSize.X"):
            extract_metadata("""
class MyStrategy(Strategy):
    universe = ["SPY"]
    cadence = Cadence(bar_size="1d")

    def on_data(self, data, portfolio):
        pass
""")