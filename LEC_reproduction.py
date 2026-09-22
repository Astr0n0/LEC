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
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde


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

    result_file = (
        workdir
        / "LEC_Results"
        / f"{atmospheric_nc.stem}_fixed"
        / f"{outname}.csv"
    )
    if not result_file.exists():
        matches = list((workdir / "LEC_Results").glob(f"**/{outname}.csv"))
        if len(matches) == 1:
            result_file = matches[0]
        else:
            raise FileNotFoundError(
                "Toolkit completed but the expected result CSV was not found: "
                f"{result_file}"
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
    """Load LorenzCycleToolkit result CSV and compute E_L and dE_L/dt."""
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"LEC result CSV not found: {path}")
    df = _read_time_indexed_csv(path)

    missing = [c for c in REQUIRED_LEC_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"LEC result file is missing required columns {missing}; "
            f"found {list(df.columns)}"
        )

    out = df.copy()
    for c in REQUIRED_LEC_COLUMNS:
        out[c] = pd.to_numeric(out[c], errors="raise")

    out["E_L"] = out[list(REQUIRED_LEC_COLUMNS)].sum(axis=1)
    seconds = (out.index - out.index[0]).total_seconds().to_numpy(dtype=float)
    if len(seconds) < 2:
        raise ValueError("At least two LEC time steps are required")
    if np.any(np.diff(seconds) <= 0):
        raise ValueError("LEC timestamps must be strictly increasing")
    out["dE_L_dt"] = np.gradient(out["E_L"].to_numpy(dtype=float), seconds)

    derivative_cols = [f"∂{term}/∂t (finite diff.)" for term in REQUIRED_LEC_COLUMNS]
    if all(c in out.columns for c in derivative_cols):
        toolkit_tendency = out[derivative_cols].sum(axis=1).to_numpy(dtype=float)
        diff = np.nanmax(np.abs(toolkit_tendency - out["dE_L_dt"].to_numpy(dtype=float)))
        scale = max(1.0, float(np.nanmax(np.abs(out["dE_L_dt"]))))
        if diff > 1e-8 * scale:
            print(
                "Warning: sum of toolkit component tendencies differs slightly from "
                f"gradient(E_L): max abs difference={diff:.6g} W/m^2"
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
    if (z < 0).any():
        raise ValueError("Precipitation contains negative values")
    return z.to_frame()


def _resample_if_requested(df: pd.DataFrame, frequency: Optional[str]) -> pd.DataFrame:
    if not frequency:
        return df
    return df.resample(frequency).mean().dropna(how="all")


def align_energy_and_radiation(
    lec: pd.DataFrame,
    radiation: pd.DataFrame,
    frequency: Optional[str] = None,
    min_abs_rn: float = 0.5,
) -> pd.DataFrame:
    """Align dE_L/dt and R_n and compute dimensionless gamma."""
    lec2 = _resample_if_requested(lec, frequency)
    rad2 = _resample_if_requested(radiation, frequency)
    merged = lec2.join(rad2[["R_n"]], how="inner")
    if merged.empty:
        raise ValueError(
            "No common timestamps between LEC and radiation. "
            "Use --resample (for example D or 6h) only if scientifically appropriate."
        )

    rn = merged["R_n"].to_numpy(dtype=float)
    bad = ~np.isfinite(rn) | (np.abs(rn) < min_abs_rn)
    if bad.any():
        print(
            f"Warning: dropping {int(bad.sum())} samples where |R_n| < {min_abs_rn} W/m^2 "
            "or R_n is non-finite; gamma would be numerically unstable there."
        )
        merged = merged.loc[~bad].copy()

    if len(merged) < 3:
        raise ValueError("Too few valid samples remain after radiation alignment")

    merged["gamma"] = merged["dE_L_dt"] / merged["R_n"]
    if not np.isfinite(merged["gamma"]).all():
        raise ValueError("gamma contains non-finite values")
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
    """Estimate p(Z|gamma) and the paper's Psi = p(Z|gamma)/p(gamma)."""
    gamma = np.asarray(gamma, dtype=float)
    z = np.asarray(z, dtype=float)
    valid = np.isfinite(gamma) & np.isfinite(z)
    gamma = gamma[valid]
    z = z[valid]
    if len(gamma) < 20:
        raise ValueError("At least 20 finite samples are recommended for 2-D KDE")
    if np.std(gamma) == 0 or np.std(z) == 0:
        raise ValueError("KDE requires non-zero variance in both gamma and Z")

    lower_g, upper_g = np.percentile(gamma, [1, 99])
    lower_z, upper_z = np.percentile(z, [0, 99.5])
    if upper_z <= lower_z:
        upper_z = float(np.max(z))
    filtered = (gamma >= lower_g) & (gamma <= upper_g) & (z >= lower_z) & (z <= upper_z)
    gf = gamma[filtered]
    zf = z[filtered]
    if len(gf) < 15:
        gf, zf = gamma, z

    kde = gaussian_kde(np.vstack([gf, zf]))
    gamma_grid = np.linspace(float(np.min(gf)), float(np.max(gf)), gamma_points)
    z_grid = np.linspace(max(0.0, float(np.min(zf))), float(np.max(zf)), z_points)
    gm, zm = np.meshgrid(gamma_grid, z_grid)
    joint = kde(np.vstack([gm.ravel(), zm.ravel()])).reshape(z_grid.size, gamma_grid.size)

    p_gamma = np.trapezoid(joint, z_grid, axis=0)
    eps = np.finfo(float).eps
    p_gamma = np.maximum(p_gamma, eps)
    conditional = joint / p_gamma[np.newaxis, :]
    psi = conditional / p_gamma[np.newaxis, :]
    return z_grid, gamma_grid, conditional, psi


def build_analysis(
    energy_gamma: pd.DataFrame,
    precipitation: pd.DataFrame,
    frequency: Optional[str] = None,
) -> AnalysisResult:
    precip = _resample_if_requested(precipitation, frequency)
    frame = energy_gamma.join(precip[["Z"]], how="inner")
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna(subset=["gamma", "Z"])
    if len(frame) < 20:
        raise ValueError(
            f"Only {len(frame)} common gamma/precipitation samples are available; need at least 20"
        )

    corr = float(frame["gamma"].corr(frame["Z"]))
    z_grid, gamma_grid, cond, psi = estimate_conditional_pdf(
        frame["gamma"].to_numpy(), frame["Z"].to_numpy()
    )
    return AnalysisResult(frame, z_grid, gamma_grid, cond, psi, corr)


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
        help="Optional pandas frequency for ALL aligned series, e.g. D or 6h",
    )
    parser.add_argument(
        "--min-abs-rn",
        type=float,
        default=0.5,
        help="Drop samples with |Rn| below this W/m^2 threshold (default 0.5)",
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
    create_plots(result, output_dir)

    summary = pd.Series(
        {
            "n_samples": len(result.frame),
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
