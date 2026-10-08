import pandas as pd
import numpy as np

for name, path in {
    "6-hourly": r"LEC_100d_real\analysis_timeseries.csv",
    "daily": r"LEC_100d_daily\analysis_timeseries.csv",
}.items():
    df = pd.read_csv(path)

    g = df["gamma"].replace([np.inf, -np.inf], np.nan).dropna()

    print(f"\n=== {name} ===")
    print(g.describe(percentiles=[0.01,0.05,0.25,0.5,0.75,0.95,0.99]).to_string())
    print("max_abs_gamma:", g.abs().max())
