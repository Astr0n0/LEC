import numpy as np
import pandas as pd

src = pd.read_csv(
    r"LEC_100d_real\analysis_timeseries.csv",
    parse_dates=["time"],
).set_index("time")

current = pd.read_csv(
    r"LEC_100d_daily\analysis_timeseries.csv",
    parse_dates=["time"],
).set_index("time")

daily = src[["E_L", "R_n", "Z"]].resample("D").mean().dropna()

seconds = (
    daily.index - daily.index[0]
).total_seconds().to_numpy(dtype=float)

daily["dE_L_dt_recomputed"] = np.gradient(
    daily["E_L"].to_numpy(dtype=float),
    seconds,
)

daily["gamma_recomputed"] = (
    daily["dE_L_dt_recomputed"] / daily["R_n"]
)

mask = (
    np.isfinite(daily["gamma_recomputed"])
    & np.isfinite(daily["Z"])
    & (daily["R_n"].abs() >= 0.5)
)

recomputed = daily.loc[mask]

common = current[["gamma", "Z"]].join(
    recomputed[["gamma_recomputed"]],
    how="inner",
)

print("current_daily_n:", len(current))
print(
    "current_daily_r:",
    current["gamma"].corr(current["Z"]),
)

print("recomputed_daily_n:", len(recomputed))
print(
    "recomputed_daily_r:",
    recomputed["gamma_recomputed"].corr(recomputed["Z"]),
)

print(
    "corr_current_vs_recomputed_gamma:",
    common["gamma"].corr(common["gamma_recomputed"]),
)

print(
    "gamma_current_std:",
    common["gamma"].std(),
)

print(
    "gamma_recomputed_std:",
    common["gamma_recomputed"].std(),
)

print(
    "max_abs_gamma_difference:",
    (common["gamma"] - common["gamma_recomputed"]).abs().max(),
)
