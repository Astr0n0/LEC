import pandas as pd
import numpy as np
from scipy.stats import spearmanr

files = {
    "6-hourly": r"LEC_100d_real\analysis_timeseries.csv",
    "daily": r"LEC_100d_daily\analysis_timeseries.csv",
}

thresholds = [0.5, 5, 10, 20, 40, 50]

for name, path in files.items():
    df = pd.read_csv(path)

    print(f"\n=== {name} ===")
    print("threshold   n      pearson      spearman")

    for threshold in thresholds:
        x = df.loc[
            np.isfinite(df["gamma"])
            & np.isfinite(df["Z"])
            & np.isfinite(df["R_n"])
            & (df["R_n"].abs() >= threshold),
            ["gamma", "Z"]
        ]

        pearson = x["gamma"].corr(x["Z"])
        spearman = spearmanr(
            x["gamma"],
            x["Z"],
            nan_policy="omit",
        ).statistic

        print(
            f"{threshold:>8} "
            f"{len(x):>4} "
            f"{pearson:>12.6f} "
            f"{spearman:>12.6f}"
        )
