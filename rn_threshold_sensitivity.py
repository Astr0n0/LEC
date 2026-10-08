import pandas as pd
import numpy as np

files = {
    "6-hourly": r"LEC_100d_real\analysis_timeseries.csv",
    "daily": r"LEC_100d_daily\analysis_timeseries.csv",
}

thresholds = [0, 0.5, 5, 10, 20, 30, 40, 50, 75, 100]

for name, path in files.items():
    df = pd.read_csv(path)

    print(f"\n=== {name} ===")
    print("threshold   n       r(gamma,Z)")

    for threshold in thresholds:
        mask = (
            np.isfinite(df["gamma"])
            & np.isfinite(df["Z"])
            & np.isfinite(df["R_n"])
            & (np.abs(df["R_n"]) >= threshold)
        )

        sub = df.loc[mask]

        if len(sub) >= 3:
            r = np.corrcoef(sub["gamma"], sub["Z"])[0, 1]
            print(f"{threshold:>8}   {len(sub):>3}     {r: .6f}")
        else:
            print(f"{threshold:>8}   {len(sub):>3}     insufficient")
