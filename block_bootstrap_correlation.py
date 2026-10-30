"""Moving-block bootstrap CIs for LEC–precipitation correlations."""

import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from temporal_validation import (
    complete_daily_windows,
    read_time_csv,
    validate_regular_time_index,
)

RNG_SEED = 20261008
N_BOOT = 10000
MAX_BOOT_ATTEMPTS = N_BOOT * 5


def safe_correlations(gamma, z):
    """Return Pearson and Spearman correlations, or None if undefined."""
    gamma = np.asarray(gamma, dtype=float)
    z = np.asarray(z, dtype=float)

    if len(gamma) < 3 or len(z) != len(gamma):
        return None

    if not np.isfinite(gamma).all() or not np.isfinite(z).all():
        return None

    if np.ptp(gamma) == 0 or np.ptp(z) == 0:
        return None

    pearson = np.corrcoef(gamma, z)[0, 1]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        spearman = spearmanr(gamma, z).statistic

    if not np.isfinite(pearson) or not np.isfinite(spearman):
        return None

    return float(pearson), float(spearman)


def moving_block_indices(n, block_size, rng):
    """Generate indices using non-circular moving blocks."""
    if block_size < 1 or block_size > n:
        raise ValueError(
            f"Invalid block size {block_size} for series length {n}."
        )

    starts = np.arange(n - block_size + 1)
    chosen = rng.choice(
        starts,
        size=int(np.ceil(n / block_size)),
        replace=True,
    )

    return np.concatenate(
        [np.arange(start, start + block_size) for start in chosen]
    )[:n]


def bootstrap_correlations(gamma, z, block_size, rng):
    """Collect N_BOOT valid bootstrap correlations."""
    n = len(gamma)
    observed = safe_correlations(gamma, z)

    if observed is None:
        raise ValueError(
            "Observed correlation is undefined for this dataset."
        )

    pearson_boot = []
    spearman_boot = []
    attempts = 0

    while (
        len(pearson_boot) < N_BOOT
        and attempts < MAX_BOOT_ATTEMPTS
    ):
        attempts += 1
        idx = moving_block_indices(n, block_size, rng)
        result = safe_correlations(gamma[idx], z[idx])

        if result is None:
            continue

        pearson_boot.append(result[0])
        spearman_boot.append(result[1])

    if len(pearson_boot) < N_BOOT:
        raise RuntimeError(
            f"Only {len(pearson_boot)} valid bootstrap samples obtained "
            f"after {attempts} attempts. Check for constant or sparse data."
        )

    return (
        observed,
        np.asarray(pearson_boot),
        np.asarray(spearman_boot),
        attempts,
    )


# Load and validate raw input timestamps.
lec = read_time_csv(r"era5_100d_fixed\paper_lec.csv")
rad = read_time_csv("radiation_100d.csv")
precip = read_time_csv("precipitation_100d.csv")

for name, frame in (
    ("LEC", lec),
    ("Radiation", rad),
    ("Precipitation", precip),
):
    validate_regular_time_index(
        frame.index,
        "6h",
        label=name,
    )

energy_columns = ["Az", "Ae", "Kz", "Ke"]
missing_energy = set(energy_columns).difference(lec.columns)
if missing_energy:
    raise ValueError(
        f"LEC data is missing columns: {sorted(missing_energy)}"
    )

if "Rn" in rad.columns:
    rn_col = "Rn"
elif "R_n" in rad.columns:
    rn_col = "R_n"
else:
    raise ValueError(
        "Radiation data must contain either 'Rn' or 'R_n'."
    )

if "Z" not in precip.columns:
    raise ValueError("Precipitation data is missing column 'Z'.")

# 3. Reconstruct the interval derivative and align all variables.
lec["E_L"] = lec[energy_columns].sum(
    axis=1,
    min_count=len(energy_columns),
)
dt_seconds = lec.index.to_series().diff().dt.total_seconds()
lec["dELdt_interval"] = lec["E_L"].diff() / dt_seconds

sixh_raw = (
    lec[["dELdt_interval"]]
    .join(rad[[rn_col]], how="inner")
    .join(precip[["Z"]], how="inner")
    .rename(columns={rn_col: "Rn"})
    .replace([np.inf, -np.inf], np.nan)
    .dropna()
)

validate_regular_time_index(
    sixh_raw.index,
    "6h",
    label="Aligned raw analysis",
)

# Use the same interval-ending derivative for both 6-hourly and daily cases.
# The previous analysis_timeseries.csv was generated from a centered gradient
# and is intentionally not used here.
sixh = sixh_raw.loc[sixh_raw["Rn"].abs() >= 0.5].copy()
sixh["gamma"] = sixh["dELdt_interval"] / sixh["Rn"]
sixh = sixh[["gamma", "Z"]].replace(
    [np.inf, -np.inf], np.nan
).dropna()

if len(sixh) < 3:
    raise ValueError("Not enough valid 6-hourly interval observations.")

# 4. Build complete, correctly aligned daily windows.
daily_means = complete_daily_windows(sixh_raw)
daily_means = daily_means.replace(
    [np.inf, -np.inf], np.nan
)

if (daily_means["Rn"] == 0).any():
    daily_means = daily_means.loc[daily_means["Rn"] != 0]

daily_means["gamma"] = (
    daily_means["dELdt_interval"] / daily_means["Rn"]
)

daily = daily_means[["gamma", "Z"]].replace(
    [np.inf, -np.inf], np.nan
).dropna()

if len(daily) < 3:
    raise ValueError("Not enough complete daily observations.")

cases = {
    "6-hourly": {"data": sixh, "block": 8},
    "Aligned daily": {"data": daily, "block": 2},
}

# 5. Estimate observed correlations and moving-block bootstrap CIs.
for case_number, (name, cfg) in enumerate(cases.items()):
    data = cfg["data"]
    gamma = data["gamma"].to_numpy(dtype=float)
    z = data["Z"].to_numpy(dtype=float)
    n = len(data)
    block = cfg["block"]

    if block > n:
        raise ValueError(
            f"{name}: block size {block} exceeds n={n}."
        )

    rng = np.random.default_rng(RNG_SEED + case_number)

    observed, pearson_boot, spearman_boot, attempts = (
        bootstrap_correlations(gamma, z, block, rng)
    )

    p_lo, p_hi = np.percentile(
        pearson_boot, [2.5, 97.5]
    )
    s_lo, s_hi = np.percentile(
        spearman_boot, [2.5, 97.5]
    )

    print(f"\n=== {name} ===")
    print("n:", n)

    if name == "Aligned daily":
        print("first_label:", data.index.min())
        print("last_label:", data.index.max())

    print("block_size:", block)
    print("bootstrap_runs_requested:", N_BOOT)
    print("bootstrap_runs_valid:", len(pearson_boot))
    print("bootstrap_attempts:", attempts)
    print(f"pearson_observed: {observed[0]:.6f}")
    print(f"pearson_95pct_CI: [{p_lo:.6f}, {p_hi:.6f}]")
    print(f"spearman_observed: {observed[1]:.6f}")
    print(f"spearman_95pct_CI: [{s_lo:.6f}, {s_hi:.6f}]")