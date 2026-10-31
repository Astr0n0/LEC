"""Circular-shift test with threshold/lag search correction.

Daily observations retain their original chronological positions.
Thresholding masks gamma values; it does not compress the time series.
"""

import warnings

import numpy as np
from scipy.stats import pearsonr

from temporal_validation import (
    complete_daily_windows,
    read_time_csv,
    validate_regular_time_index,
)


THRESHOLDS = [0.5, 5, 10, 20, 30, 40, 50]
LAGS = range(-10, 11)
MIN_N = 3


def safe_pearson(x, y):
    """Return Pearson r, or NaN when the correlation is undefined."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if len(x) < MIN_N or len(y) != len(x):
        return np.nan

    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]

    if len(x) < MIN_N:
        return np.nan
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return np.nan

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = pearsonr(x, y).statistic

    return float(result) if np.isfinite(result) else np.nan


def lagged_pairs(x, y, lag):
    """Pair x[t] with y[t + lag] on the original daily timeline."""
    if lag > 0:
        return x[:-lag], y[lag:]
    if lag < 0:
        return x[-lag:], y[:lag]
    return x, y


def max_abs_corr(gamma, z, rn):
    """Search thresholds and lags without compressing the time axis."""
    best = None

    for threshold in THRESHOLDS:
        # Preserve every day. Values failing the threshold become NaN.
        gamma_masked = np.where(
            np.abs(rn) >= threshold,
            gamma,
            np.nan,
        )

        for lag in LAGS:
            x, y = lagged_pairs(gamma_masked, z, lag)

            valid = np.isfinite(x) & np.isfinite(y)
            x_valid = x[valid]
            y_valid = y[valid]

            if len(x_valid) < MIN_N:
                continue

            r = safe_pearson(x_valid, y_valid)
            if not np.isfinite(r):
                continue

            result = {
                "threshold": threshold,
                "lag": lag,
                "n": len(x_valid),
                "r": r,
                "abs_r": abs(r),
            }

            if best is None or result["abs_r"] > best["abs_r"]:
                best = result

    return best


# Load complete daily observations through the shared strict alignment path.
from era5_analysis import load_interval_analysis

daily = load_interval_analysis(
    r"era5_100d_fixed\paper_lec.csv",
    "radiation_100d.csv",
    "precipitation_100d.csv",
    frequency="D",
    min_abs_rn=0.0,
)[["gamma", "Z", "R_n"]]

# Keep every complete day on the timeline. Undefined gamma values remain NaN
# and are masked by each threshold/lag evaluation; they are never deleted.

gamma = daily["gamma"].to_numpy(dtype=float)
z = daily["Z"].to_numpy(dtype=float)
rn = daily["Rn"].to_numpy(dtype=float)
n = len(daily)

if n < MIN_N:
    raise ValueError(
        f"Only {n} complete daily observations; "
        f"at least {MIN_N} are required."
    )

observed = max_abs_corr(gamma, z, rn)

if observed is None:
    raise ValueError(
        "No valid threshold/lag combination met the sample-size criteria."
    )

# Circularly shift the complete Z sequence, then repeat the same search.
null_results = []

for shift in range(1, n):
    shifted_z = np.roll(z, shift)
    result = max_abs_corr(gamma, shifted_z, rn)

    if result is not None:
        null_results.append(result["abs_r"])

null = np.asarray(null_results, dtype=float)

if len(null) == 0:
    raise RuntimeError("No valid circular-shift null results were produced.")

p_value = (
    1 + np.count_nonzero(null >= observed["abs_r"])
) / (1 + len(null))

print("COMPLETE ALIGNED DAILY WINDOWS")
print("n:", n)
print("first:", daily.index.min())
print("last:", daily.index.max())

print("\nBEST OBSERVED AFTER THRESHOLD/LAG SEARCH")
print("threshold:", observed["threshold"])
print("lag:", observed["lag"])
print("n:", observed["n"])
print(f"max_abs_r: {observed['abs_r']:.6f}")
print(f"signed_r: {observed['r']:.6f}")

print("\nCIRCULAR-SHIFT NULL")
print("valid_shifts:", len(null))
print(f"circular_shift_corrected_p: {p_value:.6f}")
print(f"null_95pct_max_abs_r: {np.percentile(null, 95):.6f}")
