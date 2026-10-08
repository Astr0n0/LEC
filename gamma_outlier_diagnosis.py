import pandas as pd
import numpy as np

for name, path in {
    "6-hourly": r"LEC_100d_real\analysis_timeseries.csv",
    "daily": r"LEC_100d_daily\analysis_timeseries.csv",
}.items():
    df = pd.read_csv(path, parse_dates=["time"])

    df = df.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["gamma", "R_n", "dE_L_dt", "Z"]
    )

    df["abs_gamma"] = df["gamma"].abs()
    df["abs_Rn"] = df["R_n"].abs()

    top = df.nlargest(10, "abs_gamma")[
        ["time", "gamma", "R_n", "dE_L_dt", "Z"]
    ]

    print(f"\n=== {name}: top |gamma| ===")
    print(top.to_string(index=False))

    print(
        "\ncorr(|gamma|, 1/|Rn|):",
        df["abs_gamma"].corr(1.0 / df["abs_Rn"])
    )
