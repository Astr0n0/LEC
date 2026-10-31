#!/usr/bin/env python3
"""Reproducible LEC -> radiation -> gamma -> precipitation/PDF workflow.

This script replaces the placeholder Lorenz-energy calculation in the supplied
LEC.py with LorenzCycleToolkit outputs.

Scientific definition used here (paper Eq. 10, first equality):
    gamma(t) = [d E_L(t) / dt] / R_n(t)
    E_L = Az + Ae + Kz + Ke

LorenzCycleToolkit archives Az, Ae, Kz, Ke in J m^-2, therefore their time
rate of change is W m^-2 and gamma is dimensionless when R_n is W m^-2.

For standard ERA5, LorenzCycleToolkit must normally be run with residuals
because direct friction-force components needed for Dz and De are unavailable.
The script intentionally does NOT substitute the toolkit residual terms RKz/RKe
for physical frictional dissipation in the paper's G-D expression; instead it
uses the directly diagnosed total energy tendency dE_L/dt.
"""

from __future__ import annotations

import argparse
import json
import platform
from importlib import metadata
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from scipy.stats import gaussian_kde

from temporal_validation import validate_regular_time_index


ERA5_COPERNICUS_NEW_NAMELIST = """;standard_name;Variable;Units
Air Temperature;air_temperature;t;K
Geopotential;geopotential;z;m**2/s**2
Omega Velocity;omega;w;Pa/s
Eastward Wind Component;eastward_wind;u;m/s
Northward Wind Component;northward_wind;v;m/s
Longitude;;longitude
Latitude;;latitude
Time;;valid_time
Vertical Level;;pressure_level
"""

REQUIRED_LEC_COLUMNS = ("Az", "Ae", "Kz", "Ke")


@dataclass(frozen=True)
class Domain:
    min_lon: float
    max_lon: float
    min_lat: float
    max_lat: float

    def validate(self) -> None:
        if self.min_lat >= self.max_lat:
            raise ValueError("min_lat must be smaller than max_lat")
        if not (-90 <= self.min_lat <= 90 and -90 <= self.max_lat <= 90):
            raise ValueError("latitude limits must be in [-90, 90]")
        if self.min_lon == self.max_lon:
            raise ValueError("min_lon and max_lon must define a non-zero domain")


@dataclass
class AnalysisResult:
    frame: pd.DataFrame
    z_grid: np.ndarray
    gamma_grid: np.ndarray
    conditional_pdf: np.ndarray
    psi: np.ndarray
    conditional_cdf: np.ndarray
    exceedance_probability: np.ndarray
    correlation: float


def _write_box_limits(path: Path, domain: Domain) -> None:
    domain.validate()
    path.write_text(
        "\n".join(
            [
                f"min_lon;{domain.min_lon}",
                f"max_lon;{domain.max_lon}",
                f"min_lat;{domain.min_lat}",
                f"max_lat;{domain.max_lat}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_lorenz_cycle_toolkit(
    atmospheric_nc: Path,
    output_dir: Path,
    domain: Domain,
    namelist: Optional[Path] = None,
    outname: str = "paper_lec",
) -> Path:
    """Run LorenzCycleToolkit in fixed-domain residual mode.

    A private working directory is created so the toolkit's required
    ``inputs/namelist`` file does not mutate a cloned toolkit repository.
    The installed package is invoked with ``python -m lorenzcycletoolkit``.
    """
    atmospheric_nc = atmospheric_nc.expanduser().resolve()
    if not atmospheric_nc.exists():
        raise FileNotFoundError(f"Atmospheric NetCDF not found: {atmospheric_nc}")

    output_dir = output_dir.expanduser().resolve()
    workdir = output_dir / "toolkit_work"
    inputs_dir = workdir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    namelist_target = inputs_dir / "namelist"
    if namelist is None:
        namelist_target.write_text(ERA5_COPERNICUS_NEW_NAMELIST, encoding="utf-8")
    else:
        namelist = namelist.expanduser().resolve()
        if not namelist.exists():
            raise FileNotFoundError(f"Namelist not found: {namelist}")
        shutil.copyfile(namelist, namelist_target)

    box_limits = inputs_dir / "box_limits"
    _write_box_limits(box_limits, domain)

    command = [
        sys.executable,
        "-m",
        "lorenzcycletoolkit",
        str(atmospheric_nc),
        "--fixed",
        "--residuals",
        "--box_limits",
        str(box_limits),
        "--outname",
        outname,
    ]

    print("Running LorenzCycleToolkit...")
    print(" ".join(command))
    completed = subprocess.run(
        command,
        cwd=workdir,
        text=True,
        capture_output=True,
        check=False,
    )
    (workdir / "lorenzcycletoolkit.stdout.log").write_text(
        completed.stdout, encoding="utf-8"
    )
    (workdir / "lorenzcycletoolkit.stderr.log").write_text(
        completed.stderr, encoding="utf-8"
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "LorenzCycleToolkit failed. See logs in "
            f"{workdir}. Last stderr lines:\n"
            + "\n".join(completed.stderr.splitlines()[-20:])
        )

    candidate_files = [
        atmospheric_nc.parent / f"{atmospheric_nc.stem}_fixed" / f"{outname}.csv",
        workdir
        / "LEC_Results"
        / f"{atmospheric_nc.stem}_fixed"
        / f"{outname}.csv",
    ]

    result_file = next((p for p in candidate_files if p.exists()), None)

    if result_file is None:
        matches = list(atmospheric_nc.parent.glob(f"**/{outname}.csv"))
        matches += list(workdir.glob(f"**/{outname}.csv"))

        unique_matches = list(dict.fromkeys(p.resolve() for p in matches))

        if len(unique_matches) == 1:
            result_file = unique_matches[0]
        else:
            raise FileNotFoundError(
                "Toolkit completed but the result CSV could not be uniquely located. "
                f"Found: {unique_matches}"
            )

    print(f"Toolkit results: {result_file}")
    return result_file


def _read_time_indexed_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"CSV is empty: {path}")

    time_candidates = [
        c
        for c in df.columns
        if c.lower() in {"time", "valid_time", "date", "datetime", "timestamp"}
    ]
    time_col = time_candidates[0] if time_candidates else df.columns[0]
    parsed = pd.to_datetime(df[time_col], errors="coerce")
    if parsed.isna().any():
        bad = int(parsed.isna().sum())
        raise ValueError(
            f"Could not parse {bad} timestamps from column '{time_col}' in {path}"
        )
    df = df.drop(columns=[time_col])
    df.index = pd.DatetimeIndex(parsed, name="time")
    if df.index.has_duplicates:
        raise ValueError(f"Duplicate timestamps in {path}")
    return df.sort_index()


def load_lec_results(path: Path) -> pd.DataFrame:
    """Load Toolkit reservoirs and compute interval-aligned energy tendency.

    dE_L_dt is the backward finite difference ending at each timestamp and
    aligns with ERA5 accumulations for the preceding interval. The centered
    gradient is retained separately for comparison with Toolkit diagnostics.
    """
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"LEC result CSV not found: {path}")
    df = _read_time_indexed_csv(path)
    validate_regular_time_index(df.index, "6h", label="LEC results")

    missing = [c for c in REQUIRED_LEC_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"LEC result file is missing required columns {missing}; "
            f"found {list(df.columns)}"
        )

    out = df.copy()
    for c in REQUIRED_LEC_COLUMNS:
        out[c] = pd.to_numeric(out[c], errors="raise")

    # Require all four energy reservoirs; never sum a partial energy budget.
    out[list(REQUIRED_LEC_COLUMNS)] = out[list(REQUIRED_LEC_COLUMNS)].replace(
        [np.inf, -np.inf], np.nan
    )
    out["E_L"] = out[list(REQUIRED_LEC_COLUMNS)].sum(
        axis=1, min_count=len(REQUIRED_LEC_COLUMNS)
    )

    seconds = (out.index - out.index[0]).total_seconds().to_numpy(dtype=float)
    if len(seconds) < 2:
        raise ValueError("At least two LEC time steps are required")
    intervals = np.diff(seconds)
    if np.any(~np.isfinite(intervals)) or np.any(intervals <= 0):
        raise ValueError("LEC timestamps must be strictly increasing")

    # ERA5 accumulated surface fields at timestamp t describe the interval
    # ending at t. Pair them with the matching interval-mean energy tendency.
    out["dE_L_dt"] = out["E_L"].diff() / pd.Series(
        intervals, index=out.index[1:]
    )

    # Retain the centered derivative only for diagnostics and Toolkit checks.
    out["dE_L_dt_centered"] = np.gradient(
        out["E_L"].to_numpy(dtype=float), seconds
    )

    derivative_cols = [f"∂{term}/∂t (finite diff.)" for term in REQUIRED_LEC_COLUMNS]
    if all(c in out.columns for c in derivative_cols):
        toolkit_tendency = out[derivative_cols].sum(axis=1).to_numpy(dtype=float)
        centered = out["dE_L_dt_centered"].to_numpy(dtype=float)
        valid = np.isfinite(toolkit_tendency) & np.isfinite(centered)
        if valid.any():
            diff = float(np.max(np.abs(toolkit_tendency[valid] - centered[valid])))
            scale = max(1.0, float(np.max(np.abs(centered[valid]))))
            if diff > 1e-8 * scale:
                print(
                    "Warning: sum of toolkit component tendencies differs from "
                    f"centered gradient(E_L): max abs difference={diff:.6g} W/m^2"
                )

    return out


def load_radiation_csv(path: Path) -> pd.DataFrame:
    """Load net radiation R_n [W m^-2].

    Accepted columns:
      - Rn (or R_n / net_radiation), OR
      - Q, alpha, F, with Rn = Q*(1-alpha)-F.
    """
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Radiation CSV not found: {path}")
    df = _read_time_indexed_csv(path)
    validate_regular_time_index(df.index, "6h", label="Radiation CSV")

    aliases = {c.lower(): c for c in df.columns}
    rn_col = next(
        (aliases[k] for k in ("rn", "r_n", "net_radiation", "net_radiation_flux") if k in aliases),
        None,
    )
    if rn_col is not None:
        rn = pd.to_numeric(df[rn_col], errors="raise").rename("R_n")
    else:
        required = {"q", "alpha", "f"}
        if not required.issubset(aliases):
            raise ValueError(
                "Radiation CSV must contain Rn (W/m^2), or Q, alpha, F columns"
            )
        q = pd.to_numeric(df[aliases["q"]], errors="raise")
        alpha = pd.to_numeric(df[aliases["alpha"]], errors="raise")
        f = pd.to_numeric(df[aliases["f"]], errors="raise")
        rn = (q * (1.0 - alpha) - f).rename("R_n")

    if not np.isfinite(rn.to_numpy(dtype=float)).all():
        raise ValueError("Radiation contains non-finite values.")
    return rn.to_frame()


def make_demo_radiation(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Create an explicit DEMONSTRATION-only radiation time series.

    This is not observational validation. The offset is chosen to avoid repeated
    near-zero denominators in gamma during software testing.
    """
    n = len(index)
    day = np.arange(n, dtype=float)
    q = np.full(n, 340.0)
    alpha = np.full(n, 0.30)
    # Synthetic OLR around 225 W/m^2, leaving a modest positive Rn.
    f = 225.0 + 5.0 * np.sin(2.0 * np.pi * day / 30.0)
    rn = q * (1.0 - alpha) - f
    return pd.DataFrame({"R_n": rn}, index=index)


def load_precipitation_csv(path: Path) -> pd.DataFrame:
    """Load precipitation Z [mm/day] from a time-indexed CSV."""
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Precipitation CSV not found: {path}")
    df = _read_time_indexed_csv(path)
    validate_regular_time_index(df.index, "6h", label="Precipitation CSV")
    aliases = {c.lower(): c for c in df.columns}
    z_col = next(
        (
            aliases[k]
            for k in ("z", "precipitation", "precip", "tp", "precip_mm_day")
            if k in aliases
        ),
        None,
    )
    if z_col is None:
        raise ValueError(
            "Precipitation CSV needs one of: Z, precipitation, precip, tp, precip_mm_day"
        )
    z = pd.to_numeric(df[z_col], errors="raise").rename("Z")
    if not np.isfinite(z.to_numpy(dtype=float)).all():
        raise ValueError("Precipitation contains non-finite values.")
    if (z < 0).any():
        raise ValueError("Precipitation contains negative values")
    return z.to_frame()


def _resample_if_requested(
    df: pd.DataFrame,
    frequency: Optional[str],
    required_columns: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Resample interval-ending data into complete right-labelled bins.

    Only required_columns determine whether a bin is complete. Optional
    diagnostics are averaged from available values without invalidating the
    primary LEC/radiation analysis.
    """

    if not frequency:
        return df

    try:
        target_delta = (
            pd.Timedelta(days=1)
            if frequency.strip().lower() in {"d", "1d"}
            else pd.Timedelta(frequency)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Resampling frequency must be a fixed duration that is a multiple of 6h."
        ) from exc

    six_hours = pd.Timedelta(hours=6)
    if target_delta <= pd.Timedelta(0) or target_delta % six_hours != pd.Timedelta(0):
        raise ValueError(
            "Resampling frequency must be a positive multiple of 6h (for example 6h or D)."
        )

    expected = int(target_delta / six_hours)
    resampler = df.resample(
        frequency, origin="start_day", closed="right", label="right"
    )
    counts = resampler.count()
    means = resampler.mean()
    required = list(df.columns) if required_columns is None else list(required_columns)
    missing_required = set(required).difference(df.columns)
    if missing_required:
        raise ValueError(f"Required resampling columns are missing: {sorted(missing_required)}")
    complete = counts[required].eq(expected).all(axis=1)
    result = means.loc[complete].copy()
    if len(result) > 1:
        result_intervals = result.index.to_series().diff().dropna()
        if not result_intervals.eq(target_delta).all():
            raise ValueError(
                "Complete resampled windows are not contiguous. An interior "
                "incomplete window would compress the time axis."
            )
    return result


def align_energy_and_radiation(
    lec: pd.DataFrame,
    radiation: pd.DataFrame,
    frequency: Optional[str] = None,
    min_abs_rn: float = 0.5,
) -> pd.DataFrame:
    """Align interval-ending LEC tendencies and radiation without silent joins."""
    if not np.isfinite(min_abs_rn) or min_abs_rn < 0:
        raise ValueError("min_abs_rn must be finite and non-negative.")

    lec2 = _resample_if_requested(
        lec, frequency, required_columns=["dE_L_dt"]
    )
    rad2 = _resample_if_requested(radiation, frequency)

    # The first LEC state has no preceding interval. Every subsequent tendency
    # must have one and only one matching interval-ending radiation value.
    valid_lec = lec2.loc[lec2["dE_L_dt"].notna()].copy()
    if not valid_lec.index.equals(rad2.index):
        missing_rn = valid_lec.index.difference(rad2.index)
        extra_rn = rad2.index.difference(valid_lec.index)
        raise ValueError(
            "LEC and radiation timestamps do not match exactly after "
            f"{frequency or '6-hourly'} alignment. "
            f"Missing radiation timestamps={list(missing_rn[:5])}; "
            f"unmatched radiation timestamps={list(extra_rn[:5])}."
        )

    merged = valid_lec.join(rad2[["R_n"]], how="left", validate="one_to_one")
    if merged.empty:
        raise ValueError("No complete common timestamps remain after alignment.")

    rn = merged["R_n"].to_numpy(dtype=float)
    tendency = merged["dE_L_dt"].to_numpy(dtype=float)
    stable = np.isfinite(rn) & (np.abs(rn) >= min_abs_rn) & np.isfinite(tendency)

    # Keep the complete chronological index. A small/unstable denominator
    # masks gamma at that timestamp; it must not remove the timestamp and
    # compress the time series used by downstream diagnostics.
    merged["gamma"] = np.nan
    merged.loc[stable, "gamma"] = (
        merged.loc[stable, "dE_L_dt"] / merged.loc[stable, "R_n"]
    )
    if int(stable.sum()) < 3:
        raise ValueError("Too few valid samples remain after radiation alignment")
    return merged



def simulate_precipitation_from_gamma(
    index: pd.DatetimeIndex,
    gamma: np.ndarray,
    seed: int = 42,
    theta: float = 0.15,
    base_mean: float = 3.0,
    coupling: float = 1.0,
    sigma: float = 1.0,
) -> pd.DataFrame:
    """Demonstration-only OU precipitation process influenced by gamma.

    Gamma is standardized before coupling so the stochastic parameter has a
    stable interpretation regardless of the physical magnitude of gamma.
    Because Z is explicitly driven by gamma here, correlation from this mode is
    a simulation diagnostic, not independent empirical validation.
    """
    gamma = np.asarray(gamma, dtype=float)
    if len(gamma) != len(index):
        raise ValueError("gamma and time index lengths differ")
    std = float(np.std(gamma))
    gamma_std = (gamma - float(np.mean(gamma))) / std if std > 0 else np.zeros_like(gamma)

    rng = np.random.default_rng(seed)
    z = np.zeros(len(index), dtype=float)
    z[0] = max(base_mean, 0.0)
    for i in range(1, len(index)):
        target = max(base_mean + coupling * gamma_std[i - 1], 0.0)
        dz = theta * (target - z[i - 1]) + sigma * rng.normal()
        z[i] = max(z[i - 1] + dz, 0.0)
    return pd.DataFrame({"Z": z}, index=index)


def estimate_conditional_pdf(
    gamma: np.ndarray,
    z: np.ndarray,
    gamma_points: int = 80,
    z_points: int = 120,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Estimate p(Z|gamma) and Psi=p(Z|gamma)/p(gamma) on Z >= 0.

    The gamma trimming follows the 1st/99th-percentile filter in the paper's
    Appendix. Precipitation observations are not trimmed. Because precipitation
    is non-negative, the KDE marginal p(gamma) is integrated over the positive
    Z support, rather than over an arbitrary plotting window.
    """
    gamma = np.asarray(gamma, dtype=float)
    z = np.asarray(z, dtype=float)
    valid = np.isfinite(gamma) & np.isfinite(z)
    gamma = gamma[valid]
    z = z[valid]

    if len(gamma) < 20:
        raise ValueError("At least 20 finite samples are recommended for 2-D KDE")
    if np.any(z < 0):
        raise ValueError("Precipitation values for KDE must be non-negative.")
    if np.std(gamma) == 0 or np.std(z) == 0:
        raise ValueError("KDE requires non-zero variance in both gamma and Z")

    lower_g, upper_g = np.percentile(gamma, [1, 99])
    selected = (gamma > lower_g) & (gamma < upper_g)
    gf = gamma[selected]
    zf = z[selected]
    if len(gf) < 15:
        gf, zf = gamma, z

    kde = gaussian_kde(np.vstack([gf, zf]))
    gamma_grid = np.linspace(float(np.min(gf)), float(np.max(gf)), gamma_points)

    # Integrate the joint KDE over the full non-negative precipitation support.
    # Five conditional-kernel standard deviations beyond the largest observed
    # Z captures the remaining Gaussian tail to numerical precision.
    z_bandwidth = float(np.sqrt(kde.covariance[1, 1]))
    z_upper = float(np.max(zf) + 5.0 * z_bandwidth)
    z_norm_grid = np.linspace(0.0, z_upper, max(1000, z_points * 10))
    gamma_mesh_norm, z_mesh_norm = np.meshgrid(gamma_grid, z_norm_grid)
    joint_norm = kde(
        np.vstack([gamma_mesh_norm.ravel(), z_mesh_norm.ravel()])
    ).reshape(z_norm_grid.size, gamma_grid.size)
    marginal_gamma_raw = np.trapezoid(joint_norm, z_norm_grid, axis=0)

    if not np.isfinite(marginal_gamma_raw).all() or np.any(marginal_gamma_raw <= 0):
        raise ValueError("KDE produced an invalid marginal density for gamma.")

    # Normalize the marginal on the retained gamma support. The conditional
    # density uses the corresponding unnormalized positive-support integral,
    # so each p(Z|gamma) integrates to one over Z >= 0.
    marginal_mass = float(np.trapezoid(marginal_gamma_raw, gamma_grid))
    if not np.isfinite(marginal_mass) or marginal_mass <= 0:
        raise ValueError("KDE marginal density could not be normalized.")
    marginal_gamma = marginal_gamma_raw / marginal_mass

    z_grid = np.linspace(0.0, z_upper, z_points)
    gamma_mesh, z_mesh = np.meshgrid(gamma_grid, z_grid)
    joint = kde(
        np.vstack([gamma_mesh.ravel(), z_mesh.ravel()])
    ).reshape(z_grid.size, gamma_grid.size)

    conditional = joint / marginal_gamma_raw[np.newaxis, :]
    psi = conditional / marginal_gamma[np.newaxis, :]
    return z_grid, gamma_grid, conditional, psi


def conditional_probabilities(
    z_grid: np.ndarray,
    conditional_pdf: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return F(Z|gamma) and P(Z > z_threshold | gamma) on the KDE grid."""
    z_grid = np.asarray(z_grid, dtype=float)
    density = np.asarray(conditional_pdf, dtype=float)
    if z_grid.ndim != 1 or density.ndim != 2 or density.shape[0] != z_grid.size:
        raise ValueError("Conditional PDF dimensions do not match the Z grid.")
    if z_grid.size < 2 or not np.all(np.diff(z_grid) > 0):
        raise ValueError("Z grid must be strictly increasing with at least two points.")
    if not np.isfinite(density).all() or np.any(density < 0):
        raise ValueError("Conditional PDF must be finite and non-negative.")

    cdf = cumulative_trapezoid(density, z_grid, axis=0, initial=0.0)
    final_mass = cdf[-1, :]
    if np.any(~np.isfinite(final_mass)) or np.any(final_mass <= 0):
        raise ValueError("Conditional PDF has invalid integrated probability mass.")
    cdf = cdf / final_mass[np.newaxis, :]
    cdf = np.maximum.accumulate(np.clip(cdf, 0.0, 1.0), axis=0)
    exceedance = np.clip(1.0 - cdf, 0.0, 1.0)
    return cdf, exceedance


def build_analysis(
    energy_gamma: pd.DataFrame,
    precipitation: pd.DataFrame,
    frequency: Optional[str] = None,
) -> AnalysisResult:
    precip = _resample_if_requested(precipitation, frequency)
    missing = energy_gamma.index.difference(precip.index)
    if len(missing):
        raise ValueError(
            "Precipitation is missing timestamps required by the aligned "
            f"LEC/radiation analysis: {list(missing[:5])}."
        )
    precip = precip.reindex(energy_gamma.index)
    frame = energy_gamma.join(precip[["Z"]], how="left", validate="one_to_one")
    frame = frame.replace([np.inf, -np.inf], np.nan)
    if frame["Z"].isna().any() or not np.isfinite(frame["Z"].to_numpy(dtype=float)).all():
        raise ValueError("Aligned precipitation contains missing or non-finite values.")

    valid_pairs = np.isfinite(frame["gamma"].to_numpy(dtype=float)) & np.isfinite(
        frame["Z"].to_numpy(dtype=float)
    )
    if int(valid_pairs.sum()) < 20:
        raise ValueError(
            f"Only {int(valid_pairs.sum())} finite gamma/precipitation pairs are available; need at least 20"
        )

    # Statistical summaries use pairwise-valid values, while frame retains
    # all original timestamps and masked gamma values for time-series work.
    valid_frame = frame.loc[valid_pairs]
    corr = float(valid_frame["gamma"].corr(valid_frame["Z"]))
    z_grid, gamma_grid, cond, psi = estimate_conditional_pdf(
        valid_frame["gamma"].to_numpy(), valid_frame["Z"].to_numpy()
    )
    conditional_cdf, exceedance = conditional_probabilities(z_grid, cond)
    return AnalysisResult(
        frame, z_grid, gamma_grid, cond, psi,
        conditional_cdf, exceedance, corr
    )




def _save_figure(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def create_plots(result: AnalysisResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    df = result.frame

    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(df.index, df["Z"], label="Precipitation Z [mm/day]")
    ax1.set_ylabel("Precipitation [mm/day]")
    ax1.set_xlabel("Time")
    ax2 = ax1.twinx()
    ax2.plot(df.index, df["gamma"], label="gamma", alpha=0.75)
    ax2.set_ylabel("gamma = (dE_L/dt)/R_n [-]")
    ax1.set_title("Precipitation and LEC/Radiation Energy Ratio")
    _save_figure(fig, output_dir / "01_time_series.png")

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(df["gamma"], df["Z"], alpha=0.6, s=18)
    ax.set_xlabel("gamma [-]")
    ax.set_ylabel("Precipitation Z [mm/day]")
    ax.set_title(f"Z vs gamma (Pearson r = {result.correlation:.3f})")
    _save_figure(fig, output_dir / "02_scatter.png")

    fig, ax = plt.subplots(figsize=(7, 5))
    cf = ax.contourf(result.gamma_grid, result.z_grid, result.conditional_pdf, levels=20)
    fig.colorbar(cf, ax=ax, label="p(Z | gamma)")
    ax.set_xlabel("gamma [-]")
    ax.set_ylabel("Z [mm/day]")
    ax.set_title("Conditional PDF p(Z | gamma)")
    _save_figure(fig, output_dir / "03_conditional_pdf.png")

    psi = np.nan_to_num(result.psi, nan=0.0, posinf=0.0, neginf=0.0)
    fig, ax = plt.subplots(figsize=(7, 5))
    cf = ax.contourf(result.gamma_grid, result.z_grid, psi, levels=20)
    fig.colorbar(cf, ax=ax, label="Psi")
    ax.set_xlabel("gamma [-]")
    ax.set_ylabel("Z [mm/day]")
    ax.set_title("PDF Ratio Psi(Z, gamma)")
    _save_figure(fig, output_dir / "04_pdf_ratio_psi.png")

    fig, ax = plt.subplots(figsize=(7, 5))
    cf = ax.contourf(
        result.gamma_grid,
        result.z_grid,
        result.exceedance_probability,
        levels=np.linspace(0.0, 1.0, 21),
    )
    fig.colorbar(cf, ax=ax, label="P(Z > threshold | gamma)")
    ax.set_xlabel("gamma [-]")
    ax.set_ylabel("Precipitation threshold [mm/day]")
    ax.set_title("Conditional precipitation exceedance probability")
    _save_figure(fig, output_dir / "06_precipitation_exceedance_probability.png")

    bins = np.linspace(float(df["gamma"].min()), float(df["gamma"].max()), 15)
    cats = pd.cut(df["gamma"], bins=bins, include_lowest=True)
    grouped = df.groupby(cats, observed=True).agg(gamma=("gamma", "mean"), z=("Z", "mean"))
    grouped = grouped.dropna()
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(grouped["gamma"], grouped["z"], marker="o")
    ax.set_xlabel("gamma [-]")
    ax.set_ylabel("E[Z | gamma] [mm/day]")
    ax.set_title("Conditional Expectation E[Z | gamma]")
    _save_figure(fig, output_dir / "05_conditional_expectation.png")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Paper reproduction using real LorenzCycleToolkit LEC diagnostics"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--atmospheric-nc",
        type=Path,
        help="Atmospheric pressure-level NetCDF; LorenzCycleToolkit will be run",
    )
    source.add_argument(
        "--lec-results",
        type=Path,
        help="Existing LorenzCycleToolkit fixed-results CSV",
    )

    parser.add_argument(
        "--domain",
        nargs=4,
        type=float,
        metavar=("MIN_LON", "MAX_LON", "MIN_LAT", "MAX_LAT"),
        help="Required with --atmospheric-nc",
    )
    parser.add_argument(
        "--namelist",
        type=Path,
        help="Optional LorenzCycleToolkit namelist; default is modern ERA5/Copernicus mapping",
    )
    parser.add_argument("--radiation-csv", type=Path, help="Time-indexed Rn or Q/alpha/F CSV")
    parser.add_argument(
        "--demo-radiation",
        action="store_true",
        help="Use synthetic radiation for software demonstration only",
    )
    parser.add_argument("--precipitation-csv", type=Path, help="Time-indexed precipitation CSV")
    parser.add_argument(
        "--simulate-precipitation",
        action="store_true",
        help="Generate OU precipitation driven by gamma; demonstration only",
    )
    parser.add_argument(
        "--resample",
        default=None,
        help="Optional fixed resampling interval (multiple of 6h, e.g. 6h or D); only complete right-labelled bins are retained",
    )
    parser.add_argument(
        "--min-abs-rn",
        type=float,
        default=0.5,
        help="Mask gamma when |Rn| is below this W/m^2 threshold; timestamps are retained (default 0.5)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("LEC_paper_results"))
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.atmospheric_nc is not None:
        if args.domain is None:
            raise SystemExit("--domain MIN_LON MAX_LON MIN_LAT MAX_LAT is required with --atmospheric-nc")
        domain = Domain(*args.domain)
        lec_csv = run_lorenz_cycle_toolkit(
            atmospheric_nc=args.atmospheric_nc,
            output_dir=output_dir,
            domain=domain,
            namelist=args.namelist,
        )
    else:
        lec_csv = args.lec_results

    lec = load_lec_results(lec_csv)

    if args.radiation_csv and args.demo_radiation:
        raise SystemExit("Use either --radiation-csv or --demo-radiation, not both")
    if args.radiation_csv:
        radiation = load_radiation_csv(args.radiation_csv)
    elif args.demo_radiation:
        radiation = make_demo_radiation(lec.index)
    else:
        raise SystemExit(
            "Provide --radiation-csv for scientific analysis, or --demo-radiation for a software-only test"
        )

    energy_gamma = align_energy_and_radiation(
        lec,
        radiation,
        frequency=args.resample,
        min_abs_rn=args.min_abs_rn,
    )

    if args.precipitation_csv and args.simulate_precipitation:
        raise SystemExit("Use either --precipitation-csv or --simulate-precipitation, not both")
    if args.precipitation_csv:
        precipitation = load_precipitation_csv(args.precipitation_csv)
    elif args.simulate_precipitation:
        precipitation = simulate_precipitation_from_gamma(
            energy_gamma.index,
            energy_gamma["gamma"].to_numpy(),
            seed=args.seed,
        )
    else:
        raise SystemExit(
            "Provide --precipitation-csv for analysis, or --simulate-precipitation for a demonstration"
        )

    result = build_analysis(energy_gamma, precipitation, frequency=args.resample)
    result.frame.to_csv(output_dir / "analysis_timeseries.csv", index_label="time")
    conditional_frame = pd.DataFrame(
        result.conditional_pdf,
        index=pd.Index(result.z_grid, name="Z_mm_day"),
        columns=pd.Index(result.gamma_grid, name="gamma"),
    )
    psi_frame = pd.DataFrame(
        result.psi,
        index=pd.Index(result.z_grid, name="Z_mm_day"),
        columns=pd.Index(result.gamma_grid, name="gamma"),
    )
    conditional_frame.to_csv(output_dir / "conditional_pdf.csv")
    psi_frame.to_csv(output_dir / "psi.csv")
    cdf_frame = pd.DataFrame(
        result.conditional_cdf,
        index=pd.Index(result.z_grid, name="Z_threshold_mm_day"),
        columns=pd.Index(result.gamma_grid, name="gamma"),
    )
    exceedance_frame = pd.DataFrame(
        result.exceedance_probability,
        index=pd.Index(result.z_grid, name="Z_threshold_mm_day"),
        columns=pd.Index(result.gamma_grid, name="gamma"),
    )
    cdf_frame.to_csv(output_dir / "conditional_cdf.csv")
    exceedance_frame.to_csv(
        output_dir / "precipitation_exceedance_probability.csv"
    )
    create_plots(result, output_dir)

    valid_gamma = np.isfinite(result.frame["gamma"].to_numpy(dtype=float))
    analysis_metadata = {
        "python_version": platform.python_version(),
        "packages": {},
        "lec_results_csv": str(lec_csv),
        "radiation_csv": str(args.radiation_csv) if args.radiation_csv else "synthetic demonstration",
        "precipitation_csv": str(args.precipitation_csv) if args.precipitation_csv else "synthetic demonstration",
        "resampling_frequency": args.resample or "6h",
        "timestamp_convention": "interval-ending; backward finite difference",
        "daily_window": "(previous midnight, current midnight]" if args.resample and args.resample.lower() in {"d", "1d", "24h"} else None,
        "gamma_definition": "dE_L_dt / R_n",
        "minimum_absolute_radiation_W_m2": args.min_abs_rn,
        "low_radiation_handling": "gamma is masked with NaN; timestamps are retained",
        "total_samples": int(len(result.frame)),
        "valid_gamma_samples": int(valid_gamma.sum()),
        "masked_gamma_samples": int((~valid_gamma).sum()),
        "finite_gamma_precipitation_pairs": int(valid_gamma.sum()),
        "first_timestamp": str(result.frame.index.min()),
        "last_timestamp": str(result.frame.index.max()),
        "kde_gamma_percentile_filter": [1, 99],
        "kde_precipitation_support_mm_day": [0.0, float(result.z_grid[-1])],
        "conditional_pdf_normalization": "non-negative precipitation support",
        "probability_output": "P(Z > z_threshold | gamma), with every Z threshold on the saved grid",
        "psi_interpretation": "PDF ratio from paper Eq. 40; not itself an event probability",
        "zero_precipitation_treatment": "continuous KDE; no point mass at exactly zero is estimated",
        "wet_day_probability": "requires a separately specified wet-day threshold and binary or hurdle model",
        "random_seed": args.seed,
    }
    for package in ("numpy", "pandas", "scipy", "matplotlib", "xarray", "LorenzCycleToolkit"):
        try:
            analysis_metadata["packages"][package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            analysis_metadata["packages"][package] = None
    (output_dir / "analysis_metadata.json").write_text(
        json.dumps(analysis_metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = pd.Series(
        {
            "n_samples_total": len(result.frame),
            "n_gamma_valid": int(np.isfinite(result.frame["gamma"]).sum()),
            "n_gamma_masked": int(result.frame["gamma"].isna().sum()),
            "pearson_r_gamma_Z": result.correlation,
            "gamma_mean": result.frame["gamma"].mean(),
            "gamma_std": result.frame["gamma"].std(),
            "Rn_mean_W_m2": result.frame["R_n"].mean(),
            "dELdt_mean_W_m2": result.frame["dE_L_dt"].mean(),
            "Z_mean_mm_day": result.frame["Z"].mean(),
        },
        name="value",
    )
    summary.to_csv(output_dir / "summary.csv", header=True)

    print("\nAnalysis complete")
    print(summary.to_string())
    print(f"\nResults written to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
