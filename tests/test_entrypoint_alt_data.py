from __future__ import annotations

import pandas as pd
import pytest

from src.execution.container.entrypoint import (
    AltDataState,
    json_to_alt_frames,
    precompute_slices,
)


def test_json_to_alt_frames_reconstructs_raw_revisions():
    payload = {
        "FRED.GDP": {
            "date": ["2024-01-01T00:00:00", "2024-01-01T00:00:00"],
            "value": [100.0, 101.0],
            "available_at": ["2024-02-01T00:00:00", "2024-03-01T00:00:00"],
        }
    }

    frames = json_to_alt_frames(payload)

    assert set(frames) == {"FRED.GDP"}
    frame = frames["FRED.GDP"]
    assert frame.index.tolist() == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01")]
    assert frame.columns.tolist() == ["value", "available_at"]
    assert frame["value"].tolist() == [100.0, 101.0]
    assert frame["available_at"].tolist() == [
        pd.Timestamp("2024-02-01"),
        pd.Timestamp("2024-03-01"),
    ]


def test_json_to_alt_frames_empty_payload_returns_empty_dict():
    frames = json_to_alt_frames({})

    assert frames == {}


def test_json_to_alt_frames_none_payload_returns_empty_dict():
    frames = json_to_alt_frames(None)

    assert frames == {}


def test_json_to_alt_frames_empty_series_returns_empty_frame():
    frames = json_to_alt_frames({"FRED.GDP": {"date": []}})

    assert set(frames) == {"FRED.GDP"}
    assert frames["FRED.GDP"].empty
    assert frames["FRED.GDP"].index.name == "date"


def test_json_to_alt_frames_missing_date_raises():
    with pytest.raises(ValueError, match="missing 'date'"):
        json_to_alt_frames({"FRED.GDP": {"value": [100.0]}})


def _market_frame() -> pd.DataFrame:
    index = pd.to_datetime(["2024-02-15", "2024-03-15", "2024-04-15", "2024-05-15"])
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
            [10.0, 11.0, 9.0, 10.5, 100.0],
            [11.0, 12.0, 10.0, 11.5, 110.0],
            [12.0, 13.0, 11.0, 12.5, 120.0],
            [13.0, 14.0, 12.0, 13.5, 130.0],
        ],
        index=index,
        columns=columns,
    )


def _gdp_revisions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "value": [100.0, 101.0, 200.0],
            "available_at": pd.to_datetime(["2024-02-01", "2024-03-01", "2024-05-01"]),
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-01", "2024-04-01"]),
    ).rename_axis("date")


def test_alt_data_state_applies_only_available_revisions():
    state = AltDataState({"FRED.GDP": _gdp_revisions()})

    state.advance_to(pd.Timestamp("2024-01-31"))
    assert state.latest("FRED.GDP") is None
    assert state.snapshot("FRED.GDP") == {}

    state.advance_to(pd.Timestamp("2024-02-15"))
    assert state.snapshot("FRED.GDP") == {pd.Timestamp("2024-01-01"): 100.0}
    assert state.latest("FRED.GDP") == 100.0

    state.advance_to(pd.Timestamp("2024-03-15"))
    assert state.snapshot("FRED.GDP") == {pd.Timestamp("2024-01-01"): 101.0}
    assert state.latest("FRED.GDP") == 101.0


def test_alt_data_state_does_not_apply_revision_at_exact_clock():
    frame = pd.DataFrame(
        {
            "value": [100.0],
            "available_at": pd.to_datetime(["2024-02-15 00:00:00"]),
        },
        index=pd.to_datetime(["2024-01-01"]),
    ).rename_axis("date")
    state = AltDataState({"FRED.GDP": frame})

    state.advance_to(pd.Timestamp("2024-02-15 00:00:00"))
    assert state.snapshot("FRED.GDP") == {}

    state.advance_to(pd.Timestamp("2024-02-15 00:00:01"))
    assert state.snapshot("FRED.GDP") == {pd.Timestamp("2024-01-01"): 100.0}


def test_alt_data_state_rejects_missing_value():
    frame = pd.DataFrame(
        {
            "value": [None],
            "available_at": pd.to_datetime(["2024-02-01"]),
        },
        index=pd.to_datetime(["2024-01-01"]),
    ).rename_axis("date")

    with pytest.raises(ValueError, match="missing value"):
        AltDataState({"FRED.GDP": frame})


def test_alt_data_state_rejects_missing_available_at():
    frame = pd.DataFrame(
        {
            "value": [100.0],
            "available_at": [pd.NaT],
        },
        index=pd.to_datetime(["2024-01-01"]),
    ).rename_axis("date")

    with pytest.raises(ValueError, match="missing available_at"):
        AltDataState({"FRED.GDP": frame})


def test_alt_data_state_snapshot_view_reuses_identity_until_series_changes():
    state = AltDataState({"FRED.GDP": _gdp_revisions()})

    state.advance_to(pd.Timestamp("2024-03-15"))
    first = state.snapshot_view("FRED.GDP")

    state.advance_to(pd.Timestamp("2024-04-15"))
    second = state.snapshot_view("FRED.GDP")

    state.advance_to(pd.Timestamp("2024-05-15"))
    third = state.snapshot_view("FRED.GDP")

    assert second is first
    assert third is not second
    assert third == {
        pd.Timestamp("2024-01-01"): 101.0,
        pd.Timestamp("2024-04-01"): 200.0,
    }


def test_precompute_slices_exposes_point_in_time_alt_history():
    state = AltDataState({"FRED.GDP": _gdp_revisions()})

    slices, _ = precompute_slices(_market_frame(), state)

    assert slices[pd.Timestamp("2024-02-15")].alt_series("FRED.GDP") == {
        pd.Timestamp("2024-01-01"): 100.0,
    }
    assert slices[pd.Timestamp("2024-03-15")].alt_series("FRED.GDP") == {
        pd.Timestamp("2024-01-01"): 101.0,
    }
    assert slices[pd.Timestamp("2024-04-15")].alt_series("FRED.GDP") == {
        pd.Timestamp("2024-01-01"): 101.0,
    }
    assert slices[pd.Timestamp("2024-05-15")].alt_series("FRED.GDP") == {
        pd.Timestamp("2024-01-01"): 101.0,
        pd.Timestamp("2024-04-01"): 200.0,
    }


def test_precompute_slices_reuses_alt_view_when_no_revision_lands():
    state = AltDataState({"FRED.GDP": _gdp_revisions()})

    slices, _ = precompute_slices(_market_frame(), state)

    assert slices[pd.Timestamp("2024-04-15")].alt_series("FRED.GDP") is slices[
        pd.Timestamp("2024-03-15")
    ].alt_series("FRED.GDP")
    assert slices[pd.Timestamp("2024-05-15")].alt_series("FRED.GDP") is not slices[
        pd.Timestamp("2024-04-15")
    ].alt_series("FRED.GDP")
