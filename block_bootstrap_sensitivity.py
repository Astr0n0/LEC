"""Moving-block bootstrap sensitivity analysis across block lengths."""

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

BLOCK_SIZES = {
    "6-hourly": [4, 8, 12, 16],
    "Aligned daily": [2, 3, 4, 5, 7, 10],
}


def safe_correlations(x, y):
    """Return Pearson and Spearman correlations, or None if undefined."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if len(x) < 3 or len(y) != len(x):
        return None

    if not np.isfinite(x).all() or not np.isfinite(y).all():
        return None

    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return None

    pearson = np.corrcoef(x, y)[0, 1]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        spearman = spearmanr(x, y).statistic

    if not np.isfinite(pearson) or not np.isfinite(spearman):
        return None

    return float(pearson), float(spearman)


def moving_block_indices(n, block_size, rng):
    """Generate non-circular moving-block bootstrap indices."""
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


def bootstrap_ci(x, y, block_size, rng):
    """Calculate 95% percentile CIs using valid bootstrap samples."""
    observed = safe_correlations(x, y)

    if observed is None:
        raise ValueError("Observed correlation is undefined.")

    pearson_samples = []
    spearman_samples = []
    attempts = 0
    n = len(x)

    while (
        len(pearson_samples) < N_BOOT
        and attempts < MAX_BOOT_ATTEMPTS
    ):
        attempts += 1
        idx = moving_block_indices(n, block_size, rng)
        result = safe_correlations(x[idx], y[idx])

        if result is None:
            continue

        pearson_samples.append(result[0])
        spearman_samples.append(result[1])

    if len(pearson_samples) < N_BOOT:
        raise RuntimeError(
            f"Block size {block_size}: only "
            f"{len(pearson_samples)} valid samples after "
            f"{attempts} attempts."
        )

    p_lo, p_hi = np.percentile(
        pearson_samples, [2.5, 97.5]
    )
    s_lo, s_hi = np.percentile(
        spearman_samples, [2.5, 97.5]
    )

    return {
        "pearson_low": p_lo,
        "pearson_high": p_hi,
        "spearman_low": s_lo,
        "spearman_high": s_hi,
        "valid_samples": len(pearson_samples),
        "attempts": attempts,
    }


# Load and validate raw input files.
lec = read_time_csv(r"era5_100d_fixed\paper_lec.csv")
rad = read_time_csv("radiation_100d.csv")
precip = read_time_csv("precipitation_100d.csv")

for name, frame in (
    ("LEC", lec),
    ("Radiation", rad),
    ("Precipitation", precip),
):
    validate_regular_time_index(
        frame.index, "6h", label=name
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
        "Radiation data must contain 'Rn' or 'R_n'."
    )

if "Z" not in precip.columns:
    raise ValueError("Precipitation data is missing column 'Z'.")

# Reconstruct interval energy tendency and align inputs.
lec["E_L"] = lec[energy_columns].sum(
    axis=1, min_count=len(energy_columns)
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
    sixh_raw.index, "6h", label="Aligned raw analysis"
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

# Aggregate complete, aligned daily windows.
daily_means = complete_daily_windows(sixh_raw)
daily_means = daily_means.replace(
    [np.inf, -np.inf], np.nan
)
daily_means = daily_means.loc[daily_means["Rn"].abs() >= 0.5].copy()
daily_means["gamma"] = (
    daily_means["dELdt_interval"] / daily_means["Rn"]
)
daily = daily_means[["gamma", "Z"]].replace(
    [np.inf, -np.inf], np.nan
).dropna()

cases = {
    "6-hourly": sixh,
    "Aligned daily": daily,
}

# Run sensitivity analysis over the requested block sizes.
for case_number, (name, data) in enumerate(cases.items()):
    x = data["gamma"].to_numpy(dtype=float)
    y = data["Z"].to_numpy(dtype=float)

    if safe_correlations(x, y) is None:
        raise ValueError(f"{name}: observed correlation is undefined.")

    print(f"\n=== {name} ===")
    print("n:", len(data))

    if name == "Aligned daily":
        print("first_label:", data.index.min())
        print("last_label:", data.index.max())

    print(
        "block  pearson_low pearson_high "
        "spearman_low spearman_high valid attempts"
    )

    for block_number, block_size in enumerate(
        BLOCK_SIZES[name]
    ):
        rng = np.random.default_rng(
            RNG_SEED + case_number * 100 + block_number
        )

        result = bootstrap_ci(
            x, y, block_size, rng
        )

        print(
            f"{block_size:>5}  "
            f"{result['pearson_low']:>11.6f} "
            f"{result['pearson_high']:>12.6f} "
            f"{result['spearman_low']:>12.6f} "
            f"{result['spearman_high']:>13.6f} "
            f"{result['valid_samples']:>5} "
            f"{result['attempts']:>7}"
        )