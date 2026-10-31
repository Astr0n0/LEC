from datetime import date, datetime, timedelta
from pathlib import Path

import cdsapi
import pandas as pd
import xarray as xr


START_DATE = date(2020, 1, 1)
N_DAYS = 100

OUTPUT_FILE = Path("era5_100d.nc")
PARTS_DIR = Path("era5_100d_parts")

DATASET = "reanalysis-era5-pressure-levels"

VARIABLES = [
    "geopotential",
    "temperature",
    "u_component_of_wind",
    "v_component_of_wind",
    "vertical_velocity",
]

PRESSURE_LEVELS = [
    "1000",
    "850",
    "700",
    "500",
    "300",
    "200",
    "100",
]

TIMES = [
    "00:00",
    "06:00",
    "12:00",
    "18:00",
]

AREA = [
    -17.5,  # North
    -60.0,  # West
    -42.5,  # South
    -30.0,  # East
]


def build_month_groups():
    groups = {}

    for offset in range(N_DAYS):
        current = START_DATE + timedelta(days=offset)
        key = (current.year, current.month)
        groups.setdefault(key, []).append(current.day)

    return groups


def is_valid_netcdf(path, year, month, days):
    if not path.exists():
        return False

    try:
        with xr.open_dataset(path) as ds:
            required_vars = {"z", "t", "u", "v", "w"}
            required_coords = {"valid_time", "pressure_level"}
            if not required_vars.issubset(ds.data_vars):
                return False
            if not required_coords.issubset(ds.coords):
                return False
            if ds.sizes.get("valid_time") != len(days) * len(TIMES):
                return False
            levels = {str(int(level)) for level in ds["pressure_level"].values}
            if levels != set(PRESSURE_LEVELS):
                return False

            expected = pd.DatetimeIndex([
                datetime(year, month, day, int(hour[:2]))
                for day in days
                for hour in TIMES
            ])
            actual = pd.DatetimeIndex(ds["valid_time"].values)
            return actual.equals(expected)
    except Exception:
        return False


def download_parts():
    PARTS_DIR.mkdir(exist_ok=True)

    client = cdsapi.Client()
    files = []

    for (year, month), days in build_month_groups().items():
        part_file = PARTS_DIR / f"era5_{year}_{month:02d}.nc"
        files.append(part_file)

        if is_valid_netcdf(part_file, year, month, days):
            print(f"EXISTS: {part_file}")
            continue

        if part_file.exists():
            print(f"INVALID: {part_file} -- removing")
            part_file.unlink()

        request = {
            "product_type": ["reanalysis"],
            "variable": VARIABLES,
            "year": [str(year)],
            "month": [f"{month:02d}"],
            "day": [f"{day:02d}" for day in days],
            "time": TIMES,
            "pressure_level": PRESSURE_LEVELS,
            "data_format": "netcdf",
            "download_format": "unarchived",
            "area": AREA,
        }

        print(f"Downloading {year}-{month:02d}...")
        client.retrieve(DATASET, request).download(str(part_file))
        print(f"DONE: {part_file}")

    return files


def combine_parts(files):
    datasets = []

    try:
        for file in files:
            ds = xr.open_dataset(file)

            ds = ds.drop_vars(
                ["number", "expver"],
                errors="ignore",
            )

            datasets.append(ds)

        combined = xr.concat(
            datasets,
            dim="valid_time",
            data_vars="minimal",
            coords="minimal",
            compat="override",
        )

        combined = combined.sortby("valid_time")

        expected_times = pd.date_range(
            start=START_DATE, periods=N_DAYS * len(TIMES), freq="6h"
        )
        actual_times = pd.DatetimeIndex(combined["valid_time"].values)
        if not actual_times.is_unique:
            raise ValueError("Duplicate valid_time values found across monthly files.")
        if not actual_times.equals(expected_times):
            missing = expected_times.difference(actual_times)
            unexpected = actual_times.difference(expected_times)
            raise ValueError(
                "Combined pressure-level timeline is incomplete or unexpected. "
                f"Missing={list(missing[:5])}; unexpected={list(unexpected[:5])}"
            )

        combined.to_netcdf(OUTPUT_FILE)

    finally:
        for ds in datasets:
            ds.close()

    print()
    print(f"DONE: {OUTPUT_FILE}")


if __name__ == "__main__":
    files = download_parts()
    combine_parts(files)
