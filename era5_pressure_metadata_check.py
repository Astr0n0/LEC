import xarray as xr
import numpy as np

path = "era5_100d.nc"
ds = xr.open_dataset(path)

print("=== DATASET ===")
print("dims:", dict(ds.sizes))
print("coords:", list(ds.coords))
print("data_vars:", list(ds.data_vars))

time_name = "valid_time" if "valid_time" in ds.coords else "time"
level_name = (
    "pressure_level"
    if "pressure_level" in ds.coords
    else "level"
)

t = ds[time_name]

print("\n=== TIME ===")
print("time_coord:", time_name)
print("first:", t.values[0])
print("last:", t.values[-1])
print("count:", t.size)

if t.size > 1:
    dt = (
        np.diff(t.values)
        .astype("timedelta64[s]")
        .astype(float)
        / 3600
    )
    print("unique_time_steps_hours:", np.unique(dt))

print("\n=== PRESSURE LEVELS ===")
print("level_coord:", level_name)
print("levels:", ds[level_name].values)

print("\n=== DOMAIN ===")
print(
    "latitude:",
    float(ds.latitude.min()),
    "to",
    float(ds.latitude.max()),
    "count:",
    ds.latitude.size,
)
print(
    "longitude:",
    float(ds.longitude.min()),
    "to",
    float(ds.longitude.max()),
    "count:",
    ds.longitude.size,
)

for var in ["z", "t", "u", "v", "w"]:
    x = ds[var]

    print(f"\n=== {var} ===")
    print("dims:", x.dims)
    print("shape:", x.shape)
    print("units:", x.attrs.get("units"))
    print("long_name:", x.attrs.get("long_name"))
    print("standard_name:", x.attrs.get("standard_name"))

ds.close()
