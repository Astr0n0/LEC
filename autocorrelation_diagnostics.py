import pandas as pd
import numpy as np

files = {
    "6-hourly": r"LEC_100d_real\analysis_timeseries.csv",
    "daily": r"LEC_100d_daily\analysis_timeseries.csv",
}

for name, path in files.items():
    df = pd.read_csv(path)

    print(f"\n=== {name} ===")

    for col in ["gamma", "Z"]:
        x = df[col].replace(
            [np.inf, -np.inf], np.nan
        ).dropna()

        print(f"\n{col}")

        max_lag = 20 if name == "6-hourly" else 10

        for lag in range(1, max_lag + 1):
            r = x.autocorr(lag=lag)
            print(f"lag {lag:>2}: {r: .6f}")
