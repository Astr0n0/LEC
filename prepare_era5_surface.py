#!/usr/bin/env python3
"""Prepare regional ERA5 radiation and precipitation from hourly accumulations."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from era5_surface_processing import aggregate_era5_hourly_surface
from era5_metadata import SURFACE_UNITS, validate_grib_step_types, validate_variable_units


def process_surface_dataset(
    input_file: Path,
    radiation_output: Path,
    precipitation_output: Path,
) -> dict[str, object]:
    """Create area-weighted, six-hourly Rn and precipitation CSV files."""
    with xr.open_dataset(input_file) as ds:
        required = {"tsr", "ttr", "tp"}
        missing = required.difference(ds.data_vars)
        if missing:
            raise ValueError(f"Missing ERA5 surface variables: {sorted(missing)}")

        units = {name: ds[name].attrs.get("units", "") for name in required}
        validate_variable_units(
            units, SURFACE_UNITS, dataset_label="ERA5 surface dataset"
        )
        step_types = {
            name: ds[name].attrs.get("GRIB_stepType") for name in required
        }
        step_type_verified = validate_grib_step_types(
            step_types, expected="accum", dataset_label="ERA5 surface dataset"
        )

        required_coords = {"valid_time", "latitude", "longitude"}
        missing_coords = required_coords.difference(
            set(ds.coords).union(ds.dims)
        )
        if missing_coords:
            raise ValueError(f"Missing ERA5 coordinates: {sorted(missing_coords)}")

        lat = ds["latitude"]
        weights = np.cos(np.deg2rad(lat))
        if bool((weights <= 0).any()):
            raise ValueError("Latitude weights must be positive in the selected domain.")

        regional = ds[["tsr", "ttr", "tp"]].weighted(weights).mean(
            dim=["latitude", "longitude"]
        )
        frame = regional.to_dataframe()[["tsr", "ttr", "tp"]].copy()
        frame.index = pd.DatetimeIndex(frame.index, name="time")
        frame = frame.sort_index()

    radiation, precipitation, audit = aggregate_era5_hourly_surface(frame)
    audit["grib_step_type_verified"] = bool(step_type_verified)
    audit["units"] = units
    radiation_output.parent.mkdir(parents=True, exist_ok=True)
    precipitation_output.parent.mkdir(parents=True, exist_ok=True)
    radiation.to_csv(radiation_output, index_label="time")
    precipitation.to_csv(precipitation_output, index_label="time")
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert ERA5 hourly accumulated tsr/ttr/tp to 6-hourly Rn and Z."
    )
    parser.add_argument("--input-file", type=Path, default=Path("era5_surface_100d.nc"))
    parser.add_argument("--radiation-output", type=Path, default=Path("radiation_100d.csv"))
    parser.add_argument("--precipitation-output", type=Path, default=Path("precipitation_100d.csv"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = process_surface_dataset(
        args.input_file,
        args.radiation_output,
        args.precipitation_output,
    )
    print("ERA5 surface processing audit:")
    for key, value in audit.items():
        print(f"{key}: {value}")
    print(f"Saved radiation: {args.radiation_output}")
    print(f"Saved precipitation: {args.precipitation_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
