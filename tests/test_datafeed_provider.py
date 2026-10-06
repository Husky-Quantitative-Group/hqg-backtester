from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import sys
import types

import pandas as pd

try:
    from hqg_algorithms import BarSize
except ModuleNotFoundError:
    class BarSize(Enum):
        DAILY = "daily"
        WEEKLY = "weekly"
        MONTHLY = "monthly"
        QUARTERLY = "quarterly"

    sys.modules["hqg_algorithms"] = types.SimpleNamespace(
        BarSize=BarSize,
        extract_metadata=lambda _strategy_code: None,
    )

from src.services.data_provider.datafeed_provider_alt import DataFeedAltProvider
from src.services.data_provider.datafeed_provider_securities import DataFeedSecuritiesProvider


@dataclass
class FakeMarketData:
    securities: pd.DataFrame
    alt_data: pd.DataFrame


class FakeFeed:
    def __init__(self, securities: pd.DataFrame):
        self.securities = securities
        self.calls = []

    def get_data(self, securities, alt_data, start, end):
        self.calls.append(
            {
                "securities": securities,
                "alt_data": alt_data,
                "start": start,
                "end": end,
            }
        )
        return FakeMarketData(
            securities=self.securities.copy(),
            alt_data=pd.DataFrame(),
        )


class FakeAltFeed:
    def __init__(self, alt_data: pd.DataFrame):
        self.alt_data = alt_data
        self.calls = []

    def get_data(self, securities, alt_data, start, end):
        self.calls.append(
            {
                "securities": securities,
                "alt_data": alt_data,
                "start": start,
                "end": end,
            }
        )
        return FakeMarketData(
            securities=pd.DataFrame(),
            alt_data=self.alt_data.copy(),
        )


def _securities_frame() -> pd.DataFrame:
    index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-05"])
    columns = pd.MultiIndex.from_tuples(
        [
            ("SPY", "open"),
            ("SPY", "high"),
            ("SPY", "low"),
            ("SPY", "close"),
            ("SPY", "volume"),
        ]
    )
    return pd.DataFrame(
        [
            [10.0, 12.0, 9.0, 11.0, 100.0],
            [11.0, 13.0, 10.0, 12.0, 200.0],
            [12.0, 15.0, 11.0, 14.0, 300.0],
        ],
        index=index,
        columns=columns,
    )


def _alt_frame() -> pd.DataFrame:
    index = pd.to_datetime(["2024-01-01", "2024-01-01"])
    columns = pd.MultiIndex.from_tuples(
        [
            ("FRED.GDP", "value"),
            ("FRED.GDP", "available_at"),
        ],
        names=["series_id", "field"],
    )
    return pd.DataFrame(
        [
            [100.0, pd.Timestamp("2024-02-01")],
            [101.0, pd.Timestamp("2024-03-01")],
        ],
        index=index,
        columns=columns,
    )


def _flat_securities_frame() -> pd.DataFrame:
    index = pd.to_datetime(["2024-01-02", "2024-01-03"])
    return pd.DataFrame(
        {
            "open": [10.0, 11.0],
            "high": [12.0, 13.0],
            "low": [9.0, 10.0],
            "close": [11.0, 12.0],
            "volume": [100.0, 200.0],
        },
        index=index,
    )


def _patch_parquet(monkeypatch):
    def fake_to_parquet(self, path, *args, **kwargs):
        self.to_pickle(path)

    def fake_read_parquet(path, *args, **kwargs):
        return pd.read_pickle(path)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", fake_to_parquet)
    monkeypatch.setattr(pd, "read_parquet", fake_read_parquet)


def test_datafeed_provider_uses_datafeed_get_data_for_securities(monkeypatch, tmp_path):
    _patch_parquet(monkeypatch)
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 6)
    feed = FakeFeed(_securities_frame())
    provider = DataFeedSecuritiesProvider(feed=feed, cache_dir=tmp_path)
    monkeypatch.setattr(provider, "_last_trading_day", lambda: datetime(2024, 1, 6))

    result = provider.get_data(["SPY"], start, end, BarSize.DAILY)

    assert feed.calls == [
        {
            "securities": ["SPY"],
            "alt_data": [],
            "start": datetime(2000, 1, 1),
            "end": datetime(2024, 1, 6),
        }
    ]
    assert result.equals(feed.securities)


def test_datafeed_provider_resamples_securities_to_requested_bar_size(monkeypatch, tmp_path):
    _patch_parquet(monkeypatch)
    provider = DataFeedSecuritiesProvider(feed=FakeFeed(_securities_frame()), cache_dir=tmp_path)
    monkeypatch.setattr(provider, "_last_trading_day", lambda: datetime(2024, 1, 6))

    result = provider.get_data(
        ["SPY"],
        datetime(2024, 1, 1),
        datetime(2024, 1, 6),
        BarSize.WEEKLY,
    )

    assert result.index.tolist() == [pd.Timestamp("2024-01-05")]
    assert result.loc[pd.Timestamp("2024-01-05"), ("SPY", "open")] == 10.0
    assert result.loc[pd.Timestamp("2024-01-05"), ("SPY", "high")] == 15.0
    assert result.loc[pd.Timestamp("2024-01-05"), ("SPY", "low")] == 9.0
    assert result.loc[pd.Timestamp("2024-01-05"), ("SPY", "close")] == 14.0
    assert result.loc[pd.Timestamp("2024-01-05"), ("SPY", "volume")] == 600.0


def test_datafeed_provider_reuses_symbol_cache(monkeypatch, tmp_path):
    _patch_parquet(monkeypatch)
    feed = FakeFeed(_securities_frame())
    provider = DataFeedSecuritiesProvider(feed=feed, cache_dir=tmp_path)
    monkeypatch.setattr(provider, "_last_trading_day", lambda: datetime(2024, 1, 5))

    provider.get_data(
        ["SPY"],
        datetime(2024, 1, 1),
        datetime(2024, 1, 6),
        BarSize.DAILY,
    )
    provider.get_data(
        ["SPY"],
        datetime(2024, 1, 2),
        datetime(2024, 1, 5),
        BarSize.DAILY,
    )

    assert len(feed.calls) == 1


def test_datafeed_provider_extracts_flat_single_symbol_frame(monkeypatch, tmp_path):
    _patch_parquet(monkeypatch)
    feed = FakeFeed(_flat_securities_frame())
    provider = DataFeedSecuritiesProvider(feed=feed, cache_dir=tmp_path)
    monkeypatch.setattr(provider, "_last_trading_day", lambda: datetime(2024, 1, 3))

    result = provider.get_data(
        ["SPY"],
        datetime(2024, 1, 1),
        datetime(2024, 1, 4),
        BarSize.DAILY,
    )

    assert ("SPY", "close") in result.columns
    assert result[("SPY", "close")].tolist() == [11.0, 12.0]


def test_datafeed_provider_empty_symbol_slice_wipes_result(monkeypatch, tmp_path):
    _patch_parquet(monkeypatch)
    provider = DataFeedSecuritiesProvider(feed=FakeFeed(_securities_frame()), cache_dir=tmp_path)
    monkeypatch.setattr(provider, "_last_trading_day", lambda: datetime(2024, 1, 5))

    provider.get_data(
        ["SPY"],
        datetime(2024, 1, 1),
        datetime(2024, 1, 6),
        BarSize.DAILY,
    )
    result = provider.get_data(
        ["SPY"],
        datetime(2025, 1, 1),
        datetime(2025, 1, 6),
        BarSize.DAILY,
    )

    assert result.empty
    assert ("SPY", "close") in result.columns


def test_alt_provider_uses_datafeed_get_data_for_alt_only():
    start = datetime(2024, 1, 1)
    end = datetime(2024, 6, 1)
    feed = FakeAltFeed(_alt_frame())
    provider = DataFeedAltProvider(feed=feed)

    result = provider.get_data(["FRED.GDP"], start, end)

    assert feed.calls == [
        {
            "securities": [],
            "alt_data": ["FRED.GDP"],
            "start": start,
            "end": end,
        }
    ]
    assert result.equals(feed.alt_data)
