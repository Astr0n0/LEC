"""Radiation-threshold sensitivity using interval-aligned ERA5 inputs."""

import numpy as np

from era5_analysis import load_interval_analysis

LEC_FILE = r"era5_100d_fixed\paper_lec.csv"
RADIATION_FILE = "radiation_100d.csv"
PRECIPITATION_FILE = "precipitation_100d.csv"

thresholds = [0, 0.5, 5, 10, 20, 30, 40, 50, 75, 100]

for name, frequency in (("6-hourly", "6h"), ("Aligned daily", "D")):
    df = load_interval_analysis(
        LEC_FILE,
        RADIATION_FILE,
        PRECIPITATION_FILE,
        frequency=frequency,
        min_abs_rn=0.0,
    )

    print(f"\n=== {name} ===")
    print("threshold   n       r(gamma,Z)")
    for threshold in thresholds:
        mask = (
            np.isfinite(df["gamma"])
            & np.isfinite(df["Z"])
            & (df["R_n"].abs() >= threshold)
        )
        subset = df.loc[mask]
        if len(subset) >= 3:
            r = np.corrcoef(subset["gamma"], subset["Z"])[0, 1]
            print(f"{threshold:>8}   {len(subset):>3}     {r: .6f}")
        else:
            print(f"{threshold:>8}   {len(subset):>3}     insufficient")
