"""Shared timestamp validation and daily-window construction utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd


TIME_COLUMNS = {
    "time",
    "valid_time",
    "date",
    "datetime",
    "timestamp",
}


def read_time_csv(path: str) -> pd.DataFrame:
    """Read a CSV, validate unique timestamps, and return it sorted by time."""
    df = pd.read_csv(path)

    candidates = [
        column for column in df.columns
        if column.lower() in TIME_COLUMNS
    ]
    if candidates:
        time_col = candidates[0]
    else:
        time_col = df.columns[0]

    timestamps = pd.DatetimeIndex(
        pd.to_datetime(df[time_col], errors="raise"),
        name="time",
    )

    if timestamps.hasnans:
        raise ValueError(f"{path}: timestamps contain NaT.")

    if timestamps.has_duplicates:
        duplicates = timestamps[timestamps.duplicated()].unique()
        raise ValueError(
            f"{path}: duplicate timestamps found: {list(duplicates[:5])}"
        )

    df = df.drop(columns=[time_col])
    df.index = timestamps

    return df.sort_index()


def validate_regular_time_index(
    index: pd.DatetimeIndex,
    expected_step: str = "6h",
    *,
    label: str = "series",
) -> None:
    """Require unique, strictly regular timestamps at the expected cadence."""
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError(f"{label}: expected a DatetimeIndex.")

    if len(index) < 2:
        raise ValueError(f"{label}: at least two timestamps are required.")

    if index.hasnans:
        raise ValueError(f"{label}: timestamps contain NaT.")

    if index.has_duplicates:
        raise ValueError(f"{label}: duplicate timestamps found.")

    if not index.is_monotonic_increasing:
        raise ValueError(f"{label}: timestamps are not sorted.")

    expected = pd.Timedelta(expected_step)
    intervals = index.to_series().diff().dropna()
    irregular = intervals[intervals != expected]

    if not irregular.empty:
        examples = irregular.head(5).to_dict()
        raise ValueError(
            f"{label}: found {len(irregular)} intervals that are not "
            f"{expected_step}; examples: {examples}"
        )


def complete_daily_windows(
    frame: pd.DataFrame,
    *,
    expected_samples: int = 4,
    expected_step: str = "6h",
) -> pd.DataFrame:
    """
    Aggregate right-labelled 6-hour samples into complete 24-hour windows.

    A window labelled at midnight contains samples in
    (previous midnight, current midnight]. A window is accepted only when
    it contains the expected number of rows and all timestamps have the
    expected cadence.
    """
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError("frame must have a DatetimeIndex.")

    if frame.empty:
        raise ValueError("Cannot aggregate an empty time series.")

    if frame.index.hasnans:
        raise ValueError("Input timestamps contain NaT.")

    if frame.index.has_duplicates:
        raise ValueError("Input contains duplicate timestamps.")

    frame = frame.sort_index()

    if not frame.index.is_monotonic_increasing:
        raise ValueError("Input timestamps are not sorted.")

    expected = pd.Timedelta(expected_step)
    intervals = frame.index.to_series().diff().dropna()

    if (intervals <= pd.Timedelta(0)).any():
        raise ValueError("Input timestamps must be strictly increasing.")

    # Require regular spacing across the input, rather than accepting a
    # day merely because four rows happen to fall inside its boundaries.
    irregular = intervals[intervals != expected]
    if not irregular.empty:
        raise ValueError(
            f"Input has {len(irregular)} non-{expected_step} intervals; "
            "repair or explicitly reconcile the time axis before aggregation."
        )

    resample_args = {
        "rule": "24h",
        "origin": "start_day",
        "closed": "right",
        "label": "right",
    }

    counts = frame.resample(**resample_args).count()
    daily_mean = frame.resample(**resample_args).mean()

    # All columns must have the expected number of non-null values.
    complete = counts.eq(expected_samples).all(axis=1)

    # Reject windows containing non-finite numeric values after aggregation.
    numeric_cols = daily_mean.select_dtypes(include=[np.number]).columns
    if len(numeric_cols):
        finite = np.isfinite(daily_mean[numeric_cols]).all(axis=1)
        complete &= finite

    return daily_mean.loc[complete].copy()