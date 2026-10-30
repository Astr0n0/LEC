"""Build temporally aligned ERA5 LEC/radiation/precipitation diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from temporal_validation import (
    complete_daily_windows,
    read_time_csv,
    validate_regular_time_index,
)

ENERGY_COLUMNS = ["Az", "Ae", "Kz", "Ke"]


def load_interval_analysis(
    lec_path: str | Path,
    radiation_path: str | Path,
    precipitation_path: str | Path,
    *,
    frequency: Literal["6h", "D", "daily"] = "6h",
    min_abs_rn: float = 0.5,
) -> pd.DataFrame:
    """Return interval-aligned observations with gamma, R_n, dE_L/dt and Z.

    ERA5 accumulated surface fields at time t describe the six-hour interval
    ending at t. The energy tendency is therefore the backward interval
    difference [E_L(t)-E_L(t-6h)]/6h. Daily data use complete right-labelled
    windows (previous midnight, current midnight], containing four intervals.
    """
    if not np.isfinite(min_abs_rn) or min_abs_rn < 0:
        raise ValueError("min_abs_rn must be a finite, non-negative number.")

    lec = read_time_csv(lec_path)
    radiation = read_time_csv(radiation_path)
    precipitation = read_time_csv(precipitation_path)

    for label, frame in (
        ("LEC", lec),
        ("Radiation", radiation),
        ("Precipitation", precipitation),
    ):
        validate_regular_time_index(frame.index, "6h", label=label)

    missing_energy = set(ENERGY_COLUMNS).difference(lec.columns)
    if missing_energy:
        raise ValueError(
            f"LEC file is missing energy reservoirs: {sorted(missing_energy)}"
        )

    rn_column = "Rn" if "Rn" in radiation.columns else (
        "R_n" if "R_n" in radiation.columns else None
    )
    if rn_column is None:
        raise ValueError("Radiation file must contain 'Rn' or 'R_n'.")
    if "Z" not in precipitation.columns:
        raise ValueError("Precipitation file is missing column 'Z'.")

    for column in ENERGY_COLUMNS:
        lec[column] = pd.to_numeric(lec[column], errors="raise")
    radiation[rn_column] = pd.to_numeric(
        radiation[rn_column], errors="raise"
    )
    precipitation["Z"] = pd.to_numeric(
        precipitation["Z"], errors="raise"
    )
    if (precipitation["Z"].dropna() < 0).any():
        raise ValueError("Precipitation contains negative values.")

    reservoirs = lec[ENERGY_COLUMNS].replace(
        [np.inf, -np.inf], np.nan
    )
    energy = reservoirs.sum(
        axis=1, min_count=len(ENERGY_COLUMNS)
    ).rename("E_L")

    dt_seconds = lec.index.to_series().diff().dt.total_seconds()
    tendency = (energy.diff() / dt_seconds).rename("dE_L_dt")

    frame = (
        tendency.to_frame()
        .join(radiation[[rn_column]].rename(columns={rn_column: "R_n"}), how="inner")
        .join(precipitation[["Z"]], how="inner")
        .replace([np.inf, -np.inf], np.nan)
        .dropna(subset=["dE_L_dt", "R_n", "Z"])
    )
    validate_regular_time_index(
        frame.index, "6h", label="aligned LEC/radiation/precipitation"
    )

    if frequency == "6h":
        result = frame
    elif frequency in {"D", "daily"}:
        result = complete_daily_windows(frame)
    else:
        raise ValueError("frequency must be '6h' or 'D'/'daily'.")

    result = result.copy()
    result["gamma"] = np.nan
    stable = result["R_n"].abs() >= min_abs_rn
    stable &= result["R_n"] != 0
    result.loc[stable, "gamma"] = (
        result.loc[stable, "dE_L_dt"] / result.loc[stable, "R_n"]
    )
    return result
