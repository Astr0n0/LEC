import pandas as pd
import numpy as np

lec = pd.read_csv(
    r"era5_100d_fixed\paper_lec.csv",
    parse_dates=[0],
)

time_col = lec.columns[0]
lec = lec.rename(columns={time_col: "time"}).set_index("time")

lec["E_L"] = lec[["Az", "Ae", "Kz", "Ke"]].sum(axis=1)

seconds = (
    lec.index - lec.index[0]
).total_seconds().to_numpy(dtype=float)

lec["dE_L_dt_gradient"] = np.gradient(
    lec["E_L"].to_numpy(dtype=float),
    seconds,
)

derivative_cols = [
    "∂Az/∂t (finite diff.)",
    "∂Ae/∂t (finite diff.)",
    "∂Kz/∂t (finite diff.)",
    "∂Ke/∂t (finite diff.)",
]

lec["dE_L_dt_toolkit_sum"] = lec[derivative_cols].sum(axis=1)

diff = (
    lec["dE_L_dt_gradient"]
    - lec["dE_L_dt_toolkit_sum"]
)

print("n:", len(lec))
print("max_abs_difference:", diff.abs().max())
print("mean_abs_difference:", diff.abs().mean())
print("rmse:", np.sqrt(np.mean(diff**2)))

print(
    "correlation:",
    lec["dE_L_dt_gradient"].corr(
        lec["dE_L_dt_toolkit_sum"]
    )
)

print("\n=== largest differences ===")
out = lec.assign(abs_diff=diff.abs()).nlargest(
    10,
    "abs_diff",
)[
    [
        "dE_L_dt_gradient",
        "dE_L_dt_toolkit_sum",
        "abs_diff",
    ]
]

print(out.to_string())
