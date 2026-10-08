import numpy as np
import pandas as pd
from scipy.stats import spearmanr

df = pd.read_csv(
    r"LEC_100d_real\analysis_timeseries.csv",
    parse_dates=["time"],
)

boundary_cols = ["BAz", "BAe", "BKz", "BKe"]
residual_cols = ["RGz", "RGe", "RKz", "RKe"]

df["B_total"] = df[boundary_cols].sum(axis=1)
df["R_total"] = df[residual_cols].sum(axis=1)

df["gamma_total"] = df["dE_L_dt"] / df["R_n"]

# Regional sensitivity only:
# remove diagnosed boundary contribution from total energy tendency.
df["gamma_boundary_adjusted"] = (
    (df["dE_L_dt"] - df["B_total"]) / df["R_n"]
)

df["gamma_residual_sum"] = df["R_total"] / df["R_n"]

print("=== CONSISTENCY ===")
print(
    "max |boundary_adjusted - residual_sum|:",
    (
        df["gamma_boundary_adjusted"]
        - df["gamma_residual_sum"]
    ).abs().max()
)

thresholds = [0.5, 5, 10, 20, 40, 50]

print("\n=== 6-HOURLY SENSITIVITY ===")
print(
    "threshold   n   "
    "Pearson(total)   Pearson(adj)   "
    "Spearman(total)  Spearman(adj)"
)

for threshold in thresholds:
    x = df.loc[
        np.isfinite(df["gamma_total"])
        & np.isfinite(df["gamma_boundary_adjusted"])
        & np.isfinite(df["Z"])
        & np.isfinite(df["R_n"])
        & (df["R_n"].abs() >= threshold)
    ].copy()

    p_total = x["gamma_total"].corr(x["Z"])
    p_adj = x["gamma_boundary_adjusted"].corr(x["Z"])

    s_total = spearmanr(
        x["gamma_total"], x["Z"]
    ).statistic

    s_adj = spearmanr(
        x["gamma_boundary_adjusted"], x["Z"]
    ).statistic

    print(
        f"{threshold:>8} "
        f"{len(x):>4} "
        f"{p_total:>16.6f} "
        f"{p_adj:>14.6f} "
        f"{s_total:>17.6f} "
        f"{s_adj:>14.6f}"
    )

print("\n=== DAILY SENSITIVITY ===")

daily = (
    df.set_index("time")[
        ["dE_L_dt", "B_total", "R_total", "R_n", "Z"]
    ]
    .resample("D")
    .mean()
    .dropna()
)

daily["gamma_total"] = (
    daily["dE_L_dt"] / daily["R_n"]
)

daily["gamma_boundary_adjusted"] = (
    (daily["dE_L_dt"] - daily["B_total"])
    / daily["R_n"]
)

print(
    "threshold   n   "
    "Pearson(total)   Pearson(adj)   "
    "Spearman(total)  Spearman(adj)"
)

for threshold in thresholds:
    x = daily.loc[
        np.isfinite(daily["gamma_total"])
        & np.isfinite(daily["gamma_boundary_adjusted"])
        & np.isfinite(daily["Z"])
        & np.isfinite(daily["R_n"])
        & (daily["R_n"].abs() >= threshold)
    ].copy()

    p_total = x["gamma_total"].corr(x["Z"])
    p_adj = x["gamma_boundary_adjusted"].corr(x["Z"])

    s_total = spearmanr(
        x["gamma_total"], x["Z"]
    ).statistic

    s_adj = spearmanr(
        x["gamma_boundary_adjusted"], x["Z"]
    ).statistic

    print(
        f"{threshold:>8} "
        f"{len(x):>4} "
        f"{p_total:>16.6f} "
        f"{p_adj:>14.6f} "
        f"{s_total:>17.6f} "
        f"{s_adj:>14.6f}"
    )

