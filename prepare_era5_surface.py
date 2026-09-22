import numpy as np
import pandas as pd
import xarray as xr

INPUT_FILE = "era5_surface_test.nc"
RADIATION_OUTPUT = "radiation_real.csv"
PRECIP_OUTPUT = "precipitation_real.csv"

ds = xr.open_dataset(INPUT_FILE)

required = {"tsr", "ttr", "tp"}
missing = required.difference(ds.data_vars)
if missing:
    raise ValueError(f"Missing variables: {sorted(missing)}")

lat_weights = np.cos(np.deg2rad(ds["latitude"]))
lat_weights = lat_weights / lat_weights.mean()

regional = ds[["tsr", "ttr", "tp"]].weighted(lat_weights).mean(
    dim=["latitude", "longitude"]
)

df = regional.to_dataframe()[["tsr", "ttr", "tp"]].copy()
df.index = pd.DatetimeIndex(df.index)
df = df.sort_index()

# ERA5 hourly accumulated radiation: J m^-2 during the preceding hour.
# Build complete 6-hour periods ending at 00, 06, 12 and 18 UTC.
counts = df["tsr"].resample("6h", closed="right", label="right").count()

tsr_6h = df["tsr"].resample(
    "6h", closed="right", label="right"
).sum()

ttr_6h = df["ttr"].resample(
    "6h", closed="right", label="right"
).sum()

tp_6h = df["tp"].resample(
    "6h", closed="right", label="right"
).sum()

complete = counts == 6

tsr_6h = tsr_6h.loc[complete]
ttr_6h = ttr_6h.loc[complete]
tp_6h = tp_6h.loc[complete]

# Mean net TOA radiation flux during each 6-hour interval [W m^-2].
rn = (tsr_6h + ttr_6h) / (6.0 * 3600.0)

radiation = pd.DataFrame(
    {
        "time": rn.index,
        "Rn": rn.values,
    }
)

# ERA5 tp is accumulated water depth [m].
# Convert 6-hour accumulation to equivalent mean precipitation rate [mm/day].
precip_mm_day = tp_6h * 1000.0 * (24.0 / 6.0)

precipitation = pd.DataFrame(
    {
        "time": precip_mm_day.index,
        "Z": precip_mm_day.values,
    }
)

radiation.to_csv(RADIATION_OUTPUT, index=False)
precipitation.to_csv(PRECIP_OUTPUT, index=False)

print("Radiation:")
print(radiation.to_string(index=False))
print()
print("Precipitation:")
print(precipitation.to_string(index=False))
print()
print(f"Saved: {RADIATION_OUTPUT}")
print(f"Saved: {PRECIP_OUTPUT}")
