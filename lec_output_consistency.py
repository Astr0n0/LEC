import pandas as pd
import numpy as np

lec = pd.read_csv(
    r"era5_100d_fixed\paper_lec.csv",
    parse_dates=[0],
)

time_col = lec.columns[0]
lec = lec.rename(columns={time_col: "time"}).set_index("time")

analysis = pd.read_csv(
    r"LEC_100d_real\analysis_timeseries.csv",
    parse_dates=["time"],
).set_index("time")

print("=== RAW TOOLKIT OUTPUT ===")
print("n:", len(lec))
print("first:", lec.index.min())
print("last:", lec.index.max())
print("columns:")
print(list(lec.columns))

print("\n=== ANALYSIS OUTPUT ===")
print("n:", len(analysis))
print("first:", analysis.index.min())
print("last:", analysis.index.max())

cols = ["Az", "Ae", "Kz", "Ke"]
common = lec[cols].join(
    analysis[cols],
    how="inner",
    lsuffix="_toolkit",
    rsuffix="_analysis",
)

print("\n=== ALIGNMENT ===")
print("common_n:", len(common))

for col in cols:
    diff = (
        common[f"{col}_toolkit"]
        - common[f"{col}_analysis"]
    ).abs()

    print(
        f"{col}_max_abs_difference:",
        diff.max()
    )

print(
    "\nmissing_toolkit_times_in_analysis:",
    len(lec.index.difference(analysis.index)),
)

print(
    "missing_analysis_times_in_toolkit:",
    len(analysis.index.difference(lec.index)),
)

print(
    "toolkit_only_times:",
    list(lec.index.difference(analysis.index))
)
