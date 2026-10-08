import xarray as xr
import numpy as np

path = "era5_surface_100d.nc"
ds = xr.open_dataset(path)

print("=== DATASET ===")
print("dims:", dict(ds.sizes))
print("coords:", list(ds.coords))
print("data_vars:", list(ds.data_vars))

time_name = "valid_time" if "valid_time" in ds.coords else "time"
t = ds[time_name]

print("\n=== TIME ===")
print("time_coord:", time_name)
print("first:", t.values[0])
print("last:", t.values[-1])
print("count:", t.size)

if t.size > 1:
    dt = np.diff(t.values).astype("timedelta64[s]").astype(float) / 3600
    print("unique_time_steps_hours:", np.unique(dt))

for var in ["tsr", "ttr", "tp"]:
    x = ds[var]

    print(f"\n=== {var} ===")
    print("dims:", x.dims)
    print("shape:", x.shape)
    print("attrs:")
    for key, value in x.attrs.items():
        print(f"  {key}: {value}")

    vals = x.isel({time_name: slice(0, min(3, t.size))})
    print(
        "first_3_spatial_means:",
        vals.mean(
            dim=[d for d in ["latitude", "longitude"] if d in vals.dims]
        ).values
    )

ds.close()
