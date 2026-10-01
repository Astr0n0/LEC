import numpy as np
import xarray as xr

lon = np.linspace(0, 360, 72)
lat = np.linspace(-90, 90, 36)
lev = np.array([1000, 850, 700, 500, 300, 200, 100])
time = xr.cftime_range(start="2020-01-01", periods=100, freq="D")

u = (
    20
    * np.cos(
        np.deg2rad(
            lat[np.newaxis, :, np.newaxis, np.newaxis]
        )
    )
    * np.sin(2 * np.pi * np.arange(100) / 365)[
        :, np.newaxis, np.newaxis, np.newaxis
    ]
)

v = (
    5
    * np.sin(
        np.deg2rad(
            lat[np.newaxis, :, np.newaxis, np.newaxis]
        )
    )
    * np.ones((100, 36, 72, 7))
)

T = (
    288
    - 60
    * np.cos(
        np.deg2rad(
            lat[np.newaxis, :, np.newaxis, np.newaxis]
        )
    )
    + np.random.randn(100, 36, 72, 7) * 2
)

print("u shape:", u.shape)
print("v shape:", v.shape)
print("T shape:", T.shape)

ds = xr.Dataset(
    {
        "u": (["time", "lat", "lon", "lev"], u),
        "v": (["time", "lat", "lon", "lev"], v),
        "t": (["time", "lat", "lon", "lev"], T),
    },
    coords={
        "time": time,
        "lat": lat,
        "lon": lon,
        "lev": lev,
    },
)

print(ds)