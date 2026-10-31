#!/usr/bin/env python3
"""Fetch and append the single ERA5 endpoint needed for 100 complete days.

The original 100-calendar-day request contains 400 pressure-level states
through 2020-04-09 18 UTC and 2400 surface records through 2020-04-09 23 UTC.
For 100 complete right-closed daily windows ending 2020-04-10 00 UTC, one
additional pressure-level state and one additional hourly surface record are
required. Original NetCDF files are never modified.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import cdsapi


START = pd.Timestamp("2020-01-01 00:00:00")
ENDPOINT = pd.Timestamp("2020-04-10 00:00:00")
PRESSURE_LEVELS = ["1000", "850", "700", "500", "300", "200", "100"]
AREA = [-17.5, -60.0, -42.5, -30.0]

PRESSURE_SOURCE = Path("era5_100d.nc")
SURFACE_SOURCE = Path("era5_surface_100d.nc")
PRESSURE_ENDPOINT = Path("era5_pressure_endpoint_2020-04-10.nc")
SURFACE_ENDPOINT = Path("era5_surface_endpoint_2020-04-10.nc")
PRESSURE_OUTPUT = Path("era5_100d_extended.nc")
SURFACE_OUTPUT = Path("era5_surface_100d_extended.nc")

PRESSURE_VARIABLES = [
    "geopotential",
    "temperature",
    "u_component_of_wind",
    "v_component_of_wind",
    "vertical_velocity",
]
SURFACE_VARIABLES = [
    "top_net_solar_radiation",
    "top_net_thermal_radiation",
    "total_precipitation",
]


def _time_index(path: Path) -> pd.DatetimeIndex:
    with xr.open_dataset(path) as ds:
        if "valid_time" not in ds.coords:
            raise ValueError(f"{path}: missing valid_time coordinate.")
        return pd.DatetimeIndex(ds["valid_time"].values)


def _validate_file(
    path: Path,
    *,
    variables: set[str],
    expected_time: pd.Timestamp,
    pressure_levels: list[str] | None = None,
) -> bool:
    if not path.exists():
        return False
    try:
        with xr.open_dataset(path) as ds:
            if not variables.issubset(ds.data_vars):
                return False
            actual = pd.DatetimeIndex(ds["valid_time"].values)
            if not actual.equals(pd.DatetimeIndex([expected_time])):
                return False
            if pressure_levels is not None:
                if "pressure_level" not in ds.coords:
                    return False
                levels = {str(int(x)) for x in ds["pressure_level"].values}
                if levels != set(pressure_levels):
                    return False
            return True
    except Exception:
        return False


def _download_endpoint(
    client: cdsapi.Client,
    *,
    dataset: str,
    variables: list[str],
    output: Path,
    pressure_levels: list[str] | None = None,
) -> None:
    required = {"z", "t", "u", "v", "w"} if pressure_levels else {"tsr", "ttr", "tp"}
    if _validate_file(
        output,
        variables=required,
        expected_time=ENDPOINT,
        pressure_levels=pressure_levels,
    ):
        print(f"ENDPOINT EXISTS: {output}")
        return
    if output.exists():
        raise ValueError(
            f"{output} exists but is not the expected endpoint file. "
            "Move it aside manually; this script will not overwrite it."
        )

    request = {
        "product_type": ["reanalysis"],
        "variable": variables,
        "year": [str(ENDPOINT.year)],
        "month": [f"{ENDPOINT.month:02d}"],
        "day": [f"{ENDPOINT.day:02d}"],
        "time": ["00:00"],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": AREA,
    }
    if pressure_levels is not None:
        request["pressure_level"] = pressure_levels

    temporary = output.with_name(
        output.stem + ".download.tmp" + output.suffix
    )
    if temporary.exists():
        if _validate_file(
            temporary,
            variables=required,
            expected_time=ENDPOINT,
            pressure_levels=pressure_levels,
        ):
            temporary.replace(output)
            print(f"RECOVERED VALIDATED DOWNLOAD: {output}")
            return
        raise ValueError(
            f"Incomplete temporary download exists: {temporary}. "
            "Move it aside before retrying; it was not overwritten."
        )

    print(f"Downloading {dataset} endpoint at {ENDPOINT} ...")
    client.retrieve(dataset, request).download(str(temporary))
    if not _validate_file(
        temporary,
        variables=required,
        expected_time=ENDPOINT,
        pressure_levels=pressure_levels,
    ):
        raise RuntimeError(
            f"Downloaded endpoint failed validation: {temporary}. "
            "The temporary file was retained for inspection."
        )
    temporary.replace(output)
    print(f"VALIDATED: {output}")


def _combine(
    source: Path,
    endpoint: Path,
    output: Path,
    *,
    variables: set[str],
    expected_times: pd.DatetimeIndex,
    pressure_levels: list[str] | None = None,
) -> None:
    if output.exists():
        with xr.open_dataset(output) as existing:
            actual = pd.DatetimeIndex(existing["valid_time"].values)
            if variables.issubset(existing.data_vars) and actual.equals(expected_times):
                print(f"EXTENDED FILE EXISTS: {output}")
                return
        raise ValueError(
            f"{output} already exists but does not pass validation. "
            "It was not overwritten."
        )

    with xr.open_dataset(source) as original, xr.open_dataset(endpoint) as extra:
        for label, ds in (("source", original), ("endpoint", extra)):
            missing = variables.difference(ds.data_vars)
            if missing:
                raise ValueError(f"{label} file is missing variables: {sorted(missing)}")

        for coordinate in ("latitude", "longitude"):
            if coordinate not in original.coords or coordinate not in extra.coords:
                raise ValueError(f"Missing {coordinate} coordinate.")
            if not np.array_equal(original[coordinate].values, extra[coordinate].values):
                raise ValueError(f"{coordinate} differs between source and endpoint.")

        if pressure_levels is not None:
            original_levels = {str(int(x)) for x in original["pressure_level"].values}
            extra_levels = {str(int(x)) for x in extra["pressure_level"].values}
            if original_levels != set(pressure_levels) or extra_levels != set(pressure_levels):
                raise ValueError("Pressure-level coordinates do not match the requested levels.")

        original_clean = original.drop_vars(["number", "expver"], errors="ignore")
        extra_clean = extra.drop_vars(["number", "expver"], errors="ignore")
        combined = xr.concat(
            [original_clean, extra_clean],
            dim="valid_time",
            data_vars="minimal",
            coords="minimal",
            compat="override",
        ).sortby("valid_time")

        actual = pd.DatetimeIndex(combined["valid_time"].values)
        if not actual.is_unique or not actual.equals(expected_times):
            missing = expected_times.difference(actual)
            unexpected = actual.difference(expected_times)
            raise ValueError(
                "Extended timeline is invalid. "
                f"Missing={list(missing[:5])}; unexpected={list(unexpected[:5])}."
            )

        temporary = output.with_name(output.stem + ".tmp" + output.suffix)
        if temporary.exists():
            raise ValueError(
                f"Temporary output {temporary} already exists; it was not overwritten."
            )
        combined.to_netcdf(temporary)

    temporary.replace(output)
    print(f"CREATED: {output}")


def main() -> int:
    if not PRESSURE_SOURCE.exists() or not SURFACE_SOURCE.exists():
        raise FileNotFoundError(
            "Both original ERA5 files must exist: "
            f"{PRESSURE_SOURCE} and {SURFACE_SOURCE}."
        )

    expected_pressure_base = pd.date_range(START, periods=400, freq="6h")
    expected_surface_base = pd.date_range(START, periods=2400, freq="h")
    expected_pressure_extended = pd.date_range(START, periods=401, freq="6h")
    expected_surface_extended = pd.date_range(START, periods=2401, freq="h")

    pressure_times = _time_index(PRESSURE_SOURCE)
    surface_times = _time_index(SURFACE_SOURCE)
    if not pressure_times.equals(expected_pressure_base):
        raise ValueError(
            "Original pressure-level file does not have the expected 400 "
            "six-hourly records from 2020-01-01 00 through 2020-04-09 18."
        )
    if not surface_times.equals(expected_surface_base):
        raise ValueError(
            "Original surface file does not have the expected 2400 hourly "
            "records from 2020-01-01 00 through 2020-04-09 23."
        )

    client = cdsapi.Client()
    _download_endpoint(
        client,
        dataset="reanalysis-era5-pressure-levels",
        variables=PRESSURE_VARIABLES,
        output=PRESSURE_ENDPOINT,
        pressure_levels=PRESSURE_LEVELS,
    )
    _download_endpoint(
        client,
        dataset="reanalysis-era5-single-levels",
        variables=SURFACE_VARIABLES,
        output=SURFACE_ENDPOINT,
    )

    _combine(
        PRESSURE_SOURCE,
        PRESSURE_ENDPOINT,
        PRESSURE_OUTPUT,
        variables={"z", "t", "u", "v", "w"},
        expected_times=expected_pressure_extended,
        pressure_levels=PRESSURE_LEVELS,
    )
    _combine(
        SURFACE_SOURCE,
        SURFACE_ENDPOINT,
        SURFACE_OUTPUT,
        variables={"tsr", "ttr", "tp"},
        expected_times=expected_surface_extended,
    )

    print("\nVALIDATION COMPLETE")
    print("Pressure-level records:", len(expected_pressure_extended))
    print("Surface hourly records:", len(expected_surface_extended))
    print("Expected 6-hour intervals:", 400)
    print("Expected complete daily windows:", 100)
    print("Daily labels: 2020-01-02 00:00 through 2020-04-10 00:00")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
