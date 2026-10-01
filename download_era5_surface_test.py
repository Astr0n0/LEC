from datetime import date, timedelta
from pathlib import Path

import cdsapi
import xarray as xr


START_DATE = date(2020, 1, 1)
N_DAYS = 100

OUTPUT_FILE = Path("era5_surface_100d.nc")
PARTS_DIR = Path("era5_surface_100d_parts")

DATASET = "reanalysis-era5-single-levels"

VARIABLES = [
    "top_net_solar_radiation",
    "top_net_thermal_radiation",
    "total_precipitation",
]

TIMES = [f"{hour:02d}:00" for hour in range(24)]

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


def is_valid_netcdf(path):
    if not path.exists():
        return False

    try:
        with xr.open_dataset(path) as ds:
            required = {"tsr", "ttr", "tp"}
            return required.issubset(ds.data_vars)
    except Exception:
        return False


def download_parts():
    PARTS_DIR.mkdir(exist_ok=True)

    client = cdsapi.Client()
    files = []

    for (year, month), days in build_month_groups().items():
        part_file = PARTS_DIR / f"era5_surface_{year}_{month:02d}.nc"
        files.append(part_file)

        if is_valid_netcdf(part_file):
            print(f"EXISTS: {part_file}")
            continue

        if part_file.exists():
            print(f"CORRUPT: {part_file} -- removing")
            part_file.unlink()

        request = {
            "product_type": ["reanalysis"],
            "variable": VARIABLES,
            "year": [str(year)],
            "month": [f"{month:02d}"],
            "day": [f"{day:02d}" for day in days],
            "time": TIMES,
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

        combined = combined.sel(
            valid_time=~combined.get_index("valid_time").duplicated()
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