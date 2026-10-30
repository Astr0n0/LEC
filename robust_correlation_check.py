"""Pearson/Spearman robustness checks on interval-aligned ERA5 inputs."""

import numpy as np
from scipy.stats import spearmanr

from era5_analysis import load_interval_analysis

LEC_FILE = r"era5_100d_fixed\paper_lec.csv"
RADIATION_FILE = "radiation_100d.csv"
PRECIPITATION_FILE = "precipitation_100d.csv"

thresholds = [0.5, 5, 10, 20, 40, 50]

for name, frequency in (("6-hourly", "6h"), ("Aligned daily", "D")):
    df = load_interval_analysis(
        LEC_FILE,
        RADIATION_FILE,
        PRECIPITATION_FILE,
        frequency=frequency,
        min_abs_rn=0.0,
    )

    print(f"\n=== {name} ===")
    print("threshold   n      pearson      spearman")
    for threshold in thresholds:
        mask = (
            np.isfinite(df["gamma"])
            & np.isfinite(df["Z"])
            & (df["R_n"].abs() >= threshold)
        )
        sample = df.loc[mask, ["gamma", "Z"]]
        if len(sample) < 3:
            print(f"{threshold:>8} {len(sample):>4} insufficient")
            continue

        pearson = sample["gamma"].corr(sample["Z"])
        spearman = spearmanr(sample["gamma"], sample["Z"]).statistic
        print(
            f"{threshold:>8} {len(sample):>4} "
            f"{pearson:>12.6f} {spearman:>12.6f}"
        )
