#!/usr/bin/env python3
"""Run the reproducible 100-day ERA5-to-LEC analysis pipeline."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from era5_metadata import (
    PRESSURE_UNITS,
    SURFACE_UNITS,
    validate_grib_step_types,
    validate_variable_units,
)


ROOT = Path(__file__).resolve().parent
START = pd.Timestamp("2020-01-01 00:00:00")
PRESSURE_EXTENDED = ROOT / "era5_100d_extended.nc"
SURFACE_EXTENDED = ROOT / "era5_surface_100d_extended.nc"
LEC_RESULTS = ROOT / "era5_100d_extended_fixed" / "paper_lec.csv"
RADIATION_CSV = ROOT / "radiation_100d_extended.csv"
PRECIPITATION_CSV = ROOT / "precipitation_100d_extended.csv"
SIX_HOURLY_OUTPUT = ROOT / "LEC_100d_extended_analysis"
DAILY_OUTPUT = ROOT / "LEC_100d_extended_daily_analysis"
LOG_DIR = SIX_HOURLY_OUTPUT / "pipeline_logs"

DIAGNOSTICS = [
    "regional_energy_budget_check.py",
    "lec_derivative_consistency.py",
    "lec_output_consistency.py",
    "regional_boundary_sensitivity.py",
    "block_bootstrap_correlation.py",
    "block_bootstrap_sensitivity.py",
    "circular_shift_test.py",
    "rn_threshold_sensitivity.py",
    "gamma_distribution_check.py",
    "gamma_outlier_diagnosis.py",
    "autocorrelation_diagnostics.py",
    "robust_correlation_check.py",
]


def run_step(name: str, command: list[str], *, required: bool = True) -> dict[str, object]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {name} ===")
    print("Command:", " ".join(command))
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    log_path = LOG_DIR / f"{name.lower().replace(' ', '_')}.log"
    log_path.write_text(
        completed.stdout
        + ("\n\n--- STDERR ---\n" + completed.stderr if completed.stderr else ""),
        encoding="utf-8",
    )
    status = "success" if completed.returncode == 0 else "failed"
    print(f"{status.upper()}: {log_path}")
    if completed.returncode != 0:
        print("\n".join((completed.stderr or completed.stdout).splitlines()[-15:]))
        if required:
            raise RuntimeError(f"Required pipeline step failed: {name}")
    return {
        "name": name,
        "status": status,
        "return_code": completed.returncode,
        "log": str(log_path.relative_to(ROOT)),
    }


def _valid_extended_file(
    path: Path,
    *,
    expected_times: pd.DatetimeIndex,
    required_variables: set[str],
    pressure_levels: list[int] | None = None,
) -> bool:
    if not path.is_file():
        return False
    try:
        with xr.open_dataset(path) as ds:
            if "valid_time" not in ds.coords:
                return False
            if not required_variables.issubset(ds.data_vars):
                return False
            if not pd.DatetimeIndex(ds["valid_time"].values).equals(expected_times):
                return False
            if pressure_levels is not None:
                if "pressure_level" not in ds.coords:
                    return False
                if set(map(int, ds["pressure_level"].values)) != set(pressure_levels):
                    return False
        return True
    except Exception:
        return False


def validate_extended_inputs() -> None:
    pressure_times = pd.date_range(START, periods=401, freq="6h")
    surface_times = pd.date_range(START, periods=2401, freq="h")
    if not _valid_extended_file(
        PRESSURE_EXTENDED,
        expected_times=pressure_times,
        required_variables={"z", "t", "u", "v", "w"},
        pressure_levels=[1000, 850, 700, 500, 300, 200, 100],
    ):
        raise ValueError("Extended pressure-level NetCDF failed validation.")
    if not _valid_extended_file(
        SURFACE_EXTENDED,
        expected_times=surface_times,
        required_variables={"tsr", "ttr", "tp"},
    ):
        raise ValueError("Extended surface NetCDF failed validation.")

    with xr.open_dataset(PRESSURE_EXTENDED) as pressure_ds, xr.open_dataset(SURFACE_EXTENDED) as surface_ds:
        for coordinate, expected_size, expected_min, expected_max in (
            ("latitude", 101, -42.5, -17.5),
            ("longitude", 121, -60.0, -30.0),
        ):
            pressure_values = pressure_ds[coordinate].values
            surface_values = surface_ds[coordinate].values
            if not np.array_equal(pressure_values, surface_values):
                raise ValueError(f"Pressure and surface {coordinate} grids differ.")
            if pressure_values.size != expected_size:
                raise ValueError(
                    f"Unexpected {coordinate} grid size: {pressure_values.size}; "
                    f"expected {expected_size}."
                )
            if not (
                np.isclose(float(np.min(pressure_values)), expected_min)
                and np.isclose(float(np.max(pressure_values)), expected_max)
            ):
                raise ValueError(f"Unexpected {coordinate} domain bounds.")
            if not np.allclose(np.abs(np.diff(pressure_values)), 0.25):
                raise ValueError(f"{coordinate} grid spacing is not 0.25 degrees.")

    with xr.open_dataset(PRESSURE_EXTENDED) as ds:
        validate_variable_units(
            {name: ds[name].attrs.get("units", "") for name in PRESSURE_UNITS},
            PRESSURE_UNITS,
            dataset_label="ERA5 pressure-level dataset",
        )
        pressure_step_verified = validate_grib_step_types(
            {
                name: ds[name].attrs.get("GRIB_stepType")
                for name in PRESSURE_UNITS
            },
            expected="instant",
            dataset_label="ERA5 pressure-level dataset",
        )
        if not pressure_step_verified:
            print("WARNING: pressure-level GRIB_stepType attributes are absent; units and ERA5 dataset identity remain validated.")

    with xr.open_dataset(SURFACE_EXTENDED) as ds:
        validate_variable_units(
            {name: ds[name].attrs.get("units", "") for name in SURFACE_UNITS},
            SURFACE_UNITS,
            dataset_label="ERA5 surface dataset",
        )
        surface_step_verified = validate_grib_step_types(
            {
                name: ds[name].attrs.get("GRIB_stepType")
                for name in SURFACE_UNITS
            },
            expected="accum",
            dataset_label="ERA5 surface dataset",
        )
        if not surface_step_verified:
            print("WARNING: surface GRIB_stepType attributes are absent; official ERA5 accumulation documentation is used.")


def validate_lec_results(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"LorenzCycleToolkit result not found: {path}")
    df = pd.read_csv(path)
    time_candidates = [
        c for c in df.columns
        if c.lower() in {"time", "valid_time", "date", "datetime", "timestamp"}
    ]
    time_col = time_candidates[0] if time_candidates else df.columns[0]
    times = pd.DatetimeIndex(pd.to_datetime(df[time_col], errors="raise"))
    expected = pd.date_range(START, periods=401, freq="6h")
    if not times.equals(expected):
        raise ValueError(
            "LorenzCycleToolkit output must contain 401 regular six-hourly "
            "states from 2020-01-01 00 through 2020-04-10 00 UTC."
        )
    missing = {"Az", "Ae", "Kz", "Ke"}.difference(df.columns)
    if missing:
        raise ValueError(f"LorenzCycleToolkit output is missing {sorted(missing)}.")
    reservoirs = df[["Az", "Ae", "Kz", "Ke"]].to_numpy(dtype=float)
    if not np.isfinite(reservoirs).all():
        raise ValueError("LorenzCycleToolkit output contains missing or non-finite energy reservoirs.")


def validate_analysis_output(path: Path, *, daily: bool) -> int:
    if not path.is_file():
        raise FileNotFoundError(f"Analysis output not found: {path}")
    required_outputs = [
        "analysis_timeseries.csv",
        "summary.csv",
        "conditional_pdf.csv",
        "psi.csv",
        "conditional_cdf.csv",
        "precipitation_exceedance_probability.csv",
        "analysis_metadata.json",
    ]
    missing_outputs = [
        name for name in required_outputs
        if not (path.parent / name).is_file()
    ]
    if missing_outputs:
        raise FileNotFoundError(
            f"{path.parent} is missing required analysis outputs: {missing_outputs}"
        )
    df = pd.read_csv(path)
    times = pd.DatetimeIndex(pd.to_datetime(df["time"], errors="raise"))
    if daily:
        expected = pd.date_range("2020-01-02 00:00", periods=100, freq="D")
    else:
        expected = pd.date_range("2020-01-01 06:00", periods=400, freq="6h")
    if not times.equals(expected):
        raise ValueError(
            f"{path} has {len(times)} rows but does not match the expected "
            f"{'100 daily' if daily else '400 six-hourly'} interval-ending timeline."
        )
    return len(df)


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run endpoint extension, ERA5 processing, LEC, and statistical diagnostics."
    )
    parser.add_argument(
        "--min-abs-rn",
        type=float,
        default=0.5,
        help="Mask gamma when |Rn| is below this threshold in W/m2.",
    )
    parser.add_argument(
        "--skip-diagnostics",
        action="store_true",
        help="Run the validated data/LEC pipeline but skip bootstrap and sensitivity scripts.",
    )
    args = parser.parse_args()

    run_step(
        "Run automated tests",
        [sys.executable, "-m", "unittest", "discover", "-v"],
    )

    if not PRESSURE_EXTENDED.exists() or not SURFACE_EXTENDED.exists():
        run_step(
            "Extend ERA5 endpoints",
            [sys.executable, "extend_era5_100d.py"],
        )
    else:
        print("Extended ERA5 NetCDF files already exist; checking exact timelines.")

    validate_extended_inputs()

    run_step(
        "Prepare ERA5 surface variables",
        [
            sys.executable,
            "prepare_era5_surface.py",
            "--input-file", str(SURFACE_EXTENDED),
            "--radiation-output", str(RADIATION_CSV),
            "--precipitation-output", str(PRECIPITATION_CSV),
        ],
    )

    if LEC_RESULTS.exists():
        validate_lec_results(LEC_RESULTS)
        print(f"Using validated existing LorenzCycleToolkit output: {LEC_RESULTS}")
        lec_command = [
            sys.executable, "LEC_reproduction.py",
            "--lec-results", str(LEC_RESULTS),
            "--radiation-csv", str(RADIATION_CSV),
            "--precipitation-csv", str(PRECIPITATION_CSV),
            "--min-abs-rn", str(args.min_abs_rn),
            "--output-dir", str(SIX_HOURLY_OUTPUT),
        ]
    else:
        lec_command = [
            sys.executable, "LEC_reproduction.py",
            "--atmospheric-nc", str(PRESSURE_EXTENDED),
            "--domain", "-60", "-30", "-42.5", "-17.5",
            "--radiation-csv", str(RADIATION_CSV),
            "--precipitation-csv", str(PRECIPITATION_CSV),
            "--min-abs-rn", str(args.min_abs_rn),
            "--output-dir", str(SIX_HOURLY_OUTPUT),
        ]
    run_step("Run six-hourly LEC analysis", lec_command)
    validate_lec_results(LEC_RESULTS)

    daily_command = [
        sys.executable, "LEC_reproduction.py",
        "--lec-results", str(LEC_RESULTS),
        "--radiation-csv", str(RADIATION_CSV),
        "--precipitation-csv", str(PRECIPITATION_CSV),
        "--resample", "D",
        "--min-abs-rn", str(args.min_abs_rn),
        "--output-dir", str(DAILY_OUTPUT),
    ]
    run_step("Run complete daily LEC analysis", daily_command)

    six_hourly_count = validate_analysis_output(
        SIX_HOURLY_OUTPUT / "analysis_timeseries.csv", daily=False
    )
    daily_count = validate_analysis_output(
        DAILY_OUTPUT / "analysis_timeseries.csv", daily=True
    )

    diagnostic_results = []
    if not args.skip_diagnostics:
        for script in DIAGNOSTICS:
            diagnostic_results.append(
                run_step(
                    f"Diagnostic {Path(script).stem}",
                    [sys.executable, script],
                    required=False,
                )
            )

    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        ).stdout.strip() or None
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        ).stdout.strip() or None
    except Exception:
        commit, branch = None, None

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_branch": branch,
        "git_commit": commit,
        "python": sys.version,
        "packages": {
            name: _package_version(name)
            for name in [
                "numpy", "pandas", "scipy", "matplotlib", "xarray",
                "netCDF4", "LorenzCycleToolkit", "cdsapi",
            ]
        },
        "inputs": {
            "pressure_netcdf": str(PRESSURE_EXTENDED.name),
            "surface_netcdf": str(SURFACE_EXTENDED.name),
            "lec_results": str(LEC_RESULTS.relative_to(ROOT)),
            "radiation_csv": str(RADIATION_CSV.name),
            "precipitation_csv": str(PRECIPITATION_CSV.name),
        },
        "domain": {
            "latitude_degrees": [-42.5, -17.5],
            "longitude_degrees": [-60.0, -30.0],
            "grid_resolution_degrees": 0.25,
            "grid_shape_lat_lon": [101, 121],
        },
        "analysis": {
            "six_hourly_samples": six_hourly_count,
            "complete_daily_samples": daily_count,
            "daily_window": "(previous midnight, current midnight]",
            "min_abs_rn_W_m2": args.min_abs_rn,
            "gamma": "interval-ending dE_L/dt divided by R_n",
        },
        "diagnostics": diagnostic_results,
    }
    SIX_HOURLY_OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest_path = SIX_HOURLY_OUTPUT / "pipeline_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    failures = [x for x in diagnostic_results if x["status"] != "success"]
    print("\nPIPELINE COMPLETE")
    print("Six-hourly samples:", six_hourly_count)
    print("Complete daily samples:", daily_count)
    print("Manifest:", manifest_path)
    print("Diagnostic failures:", len(failures))
    if diagnostic_results:
        summary_path = LOG_DIR / "diagnostics_summary.txt"
        summary_path.write_text(
            "\n".join(
                f"{x['name']}: {x['status']} (exit {x['return_code']}) - {x['log']}"
                for x in diagnostic_results
            ),
            encoding="utf-8",
        )
    if failures:
        print("See pipeline_logs/diagnostics_summary.txt for individual logs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
