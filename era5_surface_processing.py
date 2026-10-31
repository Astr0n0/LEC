"""ERA5 hourly accumulated surface-variable aggregation."""

from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_VARIABLES = ("tsr", "ttr", "tp")


def aggregate_era5_hourly_surface(
    hourly: pd.DataFrame,
    *,
    expected_hours_per_bin: int = 6,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Aggregate ERA5 hourly accumulations into complete interval-ending bins.

    ERA5 hourly reanalysis accumulations represent the one-hour period ending
    at each validity timestamp. They must be summed, not differenced.
    """
    if not isinstance(hourly.index, pd.DatetimeIndex):
        raise TypeError("hourly data must have a DatetimeIndex.")
    if hourly.empty:
        raise ValueError("hourly data is empty.")
    if hourly.index.hasnans:
        raise ValueError("hourly timestamps contain NaT.")
    if hourly.index.has_duplicates:
        raise ValueError("hourly timestamps contain duplicates.")
    if not hourly.index.is_monotonic_increasing:
        raise ValueError("hourly timestamps must be sorted.")
    if (
        (hourly.index.minute != 0).any()
        or (hourly.index.second != 0).any()
        or (hourly.index.microsecond != 0).any()
        or (hourly.index.nanosecond != 0).any()
    ):
        raise ValueError("ERA5 hourly timestamps must fall exactly on the hour.")
    if expected_hours_per_bin != 6:
        raise ValueError("This project currently requires six-hour aggregation.")

    missing = set(REQUIRED_VARIABLES).difference(hourly.columns)
    if missing:
        raise ValueError(f"Missing ERA5 surface variables: {sorted(missing)}")

    data = hourly.loc[:, REQUIRED_VARIABLES].apply(pd.to_numeric, errors="raise")
    data = data.replace([np.inf, -np.inf], np.nan)

    # The bin (t-6h, t] contains six one-hour accumulations ending at
    # t-5h, ..., t. A bin is complete only when all three variables have
    # six finite values.
    resample_args = {"rule": "6h", "closed": "right", "label": "right"}
    counts = data.resample(**resample_args).count()
    complete = counts.eq(6).all(axis=1)

    totals = data.resample(**resample_args).sum(min_count=6)
    totals = totals.loc[complete]
    if totals.empty:
        raise ValueError("No complete six-hour ERA5 surface intervals were found.")

    rn = (totals["tsr"] + totals["ttr"]) / (6.0 * 3600.0)
    z_mm_day = totals["tp"] * 1000.0 * 4.0

    radiation = pd.DataFrame({"Rn": rn}, index=totals.index)
    precipitation = pd.DataFrame({"Z": z_mm_day}, index=totals.index)

    if not np.isfinite(radiation.to_numpy(dtype=float)).all():
        raise ValueError("Processed radiation contains non-finite values.")
    if not np.isfinite(precipitation.to_numpy(dtype=float)).all():
        raise ValueError("Processed precipitation contains non-finite values.")
    if (precipitation["Z"] < 0).any():
        raise ValueError("ERA5 total precipitation produced a negative value.")

    audit = {
        "input_hourly_records": int(len(data)),
        "complete_six_hour_bins": int(len(totals)),
        "discarded_incomplete_bins": int((~complete).sum()),
        "first_complete_interval_end": str(totals.index.min()),
        "last_complete_interval_end": str(totals.index.max()),
        "hourly_first_timestamp": str(data.index.min()),
        "hourly_last_timestamp": str(data.index.max()),
    }
    return radiation, precipitation, audit
