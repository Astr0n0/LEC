import pandas as pd
import numpy as np

df = pd.read_csv(
    r"era5_100d_fixed\paper_lec.csv",
    parse_dates=[0],
)

time_col = df.columns[0]
df = df.rename(columns={time_col: "time"}).set_index("time")

boundary_cols = ["BAz", "BAe", "BKz", "BKe"]
residual_cols = ["RGz", "RGe", "RKz", "RKe"]
derivative_cols = [
    "∂Az/∂t (finite diff.)",
    "∂Ae/∂t (finite diff.)",
    "∂Kz/∂t (finite diff.)",
    "∂Ke/∂t (finite diff.)",
]

df["dELdt"] = df[derivative_cols].sum(axis=1)
df["B_total"] = df[boundary_cols].sum(axis=1)
df["R_total"] = df[residual_cols].sum(axis=1)

closure = df["dELdt"] - (df["B_total"] + df["R_total"])

print("=== TOTAL ENERGY BUDGET ===")
print("n:", len(df))

for col in ["dELdt", "B_total", "R_total"]:
    x = df[col]
    print(f"\n{col}")
    print("mean:", x.mean())
    print("std:", x.std())
    print("mean_abs:", x.abs().mean())
    print("max_abs:", x.abs().max())

print("\n=== CLOSURE ===")
print("max_abs_closure:", closure.abs().max())
print("mean_abs_closure:", closure.abs().mean())

print("\n=== RELATIVE IMPORTANCE ===")
print(
    "mean_abs_boundary / mean_abs_dELdt:",
    df["B_total"].abs().mean() / df["dELdt"].abs().mean()
)

print(
    "corr(dELdt, B_total):",
    df["dELdt"].corr(df["B_total"])
)

print(
    "corr(dELdt, R_total):",
    df["dELdt"].corr(df["R_total"])
)
