# tests.test_data_cache
"""
Unit tests for the YFDataProvider parquet cache.

All tests redirect DATA_CACHE_DIR to a temporary directory and mock
yf.download() so no network calls are made.
"""

import threading
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call

import pandas as pd
import pytest

from src.services.data_provider.yf_provider import YFDataProvider
import src.services.data_provider.yf_provider as yf_provider_module


# ------------------------------------------------------------------ fixtures


START = datetime(2022, 1, 1)
END = datetime(2022, 12, 31)
BAR_SIZE = timedelta(days=1)


def _make_ohlcv_flat(n: int = 10) -> pd.DataFrame:
    """Single-ticker yf.download() response (flat columns)."""
    idx = pd.date_range("2022-01-03", periods=n, freq="B")
    return pd.DataFrame(
        {
            "Open": [100.0] * n,
            "High": [105.0] * n,
            "Low": [95.0] * n,
            "Close": [102.0] * n,
            "Volume": [1_000_000] * n,
        },
        index=idx,
    )


def _make_ohlcv_multi(symbols: list[str], n: int = 10) -> pd.DataFrame:
    """Multi-ticker yf.download(group_by='ticker') response (MultiIndex columns)."""
    idx = pd.date_range("2022-01-03", periods=n, freq="B")
    cols = pd.MultiIndex.from_product([symbols, ["Close", "High", "Low", "Open", "Volume"]])
    data = pd.DataFrame(1.0, index=idx, columns=cols)
    return data


@pytest.fixture(autouse=True)
def reset_cache_locks():
    """Clear module-level lock dict between tests to avoid cross-test state."""
    yf_provider_module._cache_locks.clear()
    yield
    yf_provider_module._cache_locks.clear()


# -------------------------------------------------------------------- tests


def test_cache_hit(tmp_path, monkeypatch):
    """
    Second call with identical args must not invoke yf.download().
    """
    monkeypatch.setattr("src.config.settings.settings.DATA_CACHE_DIR", str(tmp_path))

    provider = YFDataProvider()
    fake_data = _make_ohlcv_flat()

    with patch("yfinance.download", return_value=fake_data) as mock_dl:
        provider.get_data(["SPY"], START, END, BAR_SIZE)
        provider.get_data(["SPY"], START, END, BAR_SIZE)

    mock_dl.assert_called_once()


def test_partial_hit(tmp_path, monkeypatch):
    """
    Second request with a new symbol should fetch only the new symbol.
    """
    monkeypatch.setattr("src.config.settings.settings.DATA_CACHE_DIR", str(tmp_path))

    provider = YFDataProvider()

    first_response = _make_ohlcv_multi(["AAPL", "SPY"])
    second_response = _make_ohlcv_flat()  # only MSFT is missing

    with patch("yfinance.download", side_effect=[first_response, second_response]) as mock_dl:
        provider.get_data(["SPY", "AAPL"], START, END, BAR_SIZE)
        provider.get_data(["SPY", "MSFT"], START, END, BAR_SIZE)

    assert mock_dl.call_count == 2
    # First call fetches both missing; second call fetches only MSFT
    first_call_tickers = sorted(mock_dl.call_args_list[0].kwargs["tickers"])
    second_call_tickers = mock_dl.call_args_list[1].kwargs["tickers"]
    assert first_call_tickers == ["AAPL", "SPY"]
    assert second_call_tickers == ["MSFT"]


def test_concurrent_identical(tmp_path, monkeypatch):
    """
    13 threads requesting the same (symbol, date range) must trigger exactly
    one yf.download() call. No KeyError or race condition should occur.
    """
    monkeypatch.setattr("src.config.settings.settings.DATA_CACHE_DIR", str(tmp_path))

    n_threads = 13
    barrier = threading.Barrier(n_threads)
    errors: list[Exception] = []
    results: list[pd.DataFrame] = []
    lock = threading.Lock()

    fake_data = _make_ohlcv_flat()

    def worker():
        try:
            provider = YFDataProvider()
            barrier.wait()  # all threads start simultaneously
            df = provider.get_data(["SPY"], START, END, BAR_SIZE)
            with lock:
                results.append(df)
        except Exception as exc:
            with lock:
                errors.append(exc)

    with patch("yfinance.download", return_value=fake_data) as mock_dl:
        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert not errors, f"Thread errors: {errors}"
    assert len(results) == n_threads, "Not all threads returned a result"
    assert mock_dl.call_count == 1, (
        f"Expected 1 yf.download() call, got {mock_dl.call_count}"
    )


def test_concurrent_different(tmp_path, monkeypatch):
    """
    Threads requesting distinct symbols must not serialize on the same lock —
    each symbol acquires a different key and fetches independently.
    The total yf.download() call count must equal the number of distinct symbols.
    """
    monkeypatch.setattr("src.config.settings.settings.DATA_CACHE_DIR", str(tmp_path))

    symbols = ["SPY", "AAPL", "MSFT", "GLD", "TLT"]
    barrier = threading.Barrier(len(symbols))
    errors: list[Exception] = []
    lock = threading.Lock()

    def worker(sym: str):
        try:
            provider = YFDataProvider()
            barrier.wait()
            provider.get_data([sym], START, END, BAR_SIZE)
        except Exception as exc:
            with lock:
                errors.append(exc)

    with patch("yfinance.download", side_effect=lambda **kw: _make_ohlcv_flat()) as mock_dl:
        threads = [threading.Thread(target=worker, args=(s,)) for s in symbols]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert not errors, f"Thread errors: {errors}"
    assert mock_dl.call_count == len(symbols), (
        f"Expected {len(symbols)} yf.download() calls (one per symbol), got {mock_dl.call_count}"
    )
