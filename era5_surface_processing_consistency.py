import numpy as np
import pandas as pd
import xarray as xr

ds = xr.open_dataset("era5_surface_100d.nc")

lat_weights = np.cos(np.deg2rad(ds["latitude"]))

regional = ds[["tsr", "ttr", "tp"]].weighted(
    lat_weights
).mean(dim=["latitude", "longitude"])

raw = regional.to_dataframe()[["tsr", "ttr", "tp"]]
raw.index = pd.DatetimeIndex(raw.index)
raw = raw.sort_index()

counts = raw["tsr"].resample(
    "6h", closed="right", label="right"
).count()

tsr = raw["tsr"].resample(
    "6h", closed="right", label="right"
).sum()

ttr = raw["ttr"].resample(
    "6h", closed="right", label="right"
).sum()

tp = raw["tp"].resample(
    "6h", closed="right", label="right"
).sum()

complete = counts == 6

expected_rn = ((tsr + ttr) / (6 * 3600)).loc[complete]
expected_z = (tp * 1000 * 4).loc[complete]

rad = pd.read_csv(
    "radiation_100d.csv",
    parse_dates=["time"],
).set_index("time")["Rn"]

precip = pd.read_csv(
    "precipitation_100d.csv",
    parse_dates=["time"],
).set_index("time")["Z"]

print("=== radiation ===")
print("expected_n:", len(expected_rn))
print("csv_n:", len(rad))
print("expected_first:", expected_rn.index.min())
print("expected_last:", expected_rn.index.max())
print("csv_first:", rad.index.min())
print("csv_last:", rad.index.max())

r = pd.concat(
    [expected_rn.rename("expected"), rad.rename("csv")],
    axis=1,
    join="inner",
)

print("common_n:", len(r))
print(
    "max_abs_difference:",
    (r["expected"] - r["csv"]).abs().max(),
)

print("\n=== precipitation ===")
print("expected_n:", len(expected_z))
print("csv_n:", len(precip))
print("expected_first:", expected_z.index.min())
print("expected_last:", expected_z.index.max())
print("csv_first:", precip.index.min())
print("csv_last:", precip.index.max())

z = pd.concat(
    [expected_z.rename("expected"), precip.rename("csv")],
    axis=1,
    join="inner",
)

print("common_n:", len(z))
print(
    "max_abs_difference:",
    (z["expected"] - z["csv"]).abs().max(),
)

ds.close()
