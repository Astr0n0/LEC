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

u = np.broadcast_to(u, (100, 36, 72, 7)).copy()

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

def lorenz_energy_cycle_simple(u, v, T, lat, lev):
    # Zonal means
    u_zm = u.mean(axis=2)
    v_zm = v.mean(axis=2)
    T_zm = T.mean(axis=2)

    # Eddy variances
    u_eddy2 = ((u - u_zm[:, :, np.newaxis, :])**2).mean(axis=2)
    v_eddy2 = ((v - v_zm[:, :, np.newaxis, :])**2).mean(axis=2)
    T_eddy2 = ((T - T_zm[:, :, np.newaxis, :])**2).mean(axis=2)

    # Simple energy calculations (placeholder)
    KZ = 0.5 * (u_zm**2 + v_zm**2).mean(axis=(1, 2))
    KE = 0.5 * (u_eddy2 + v_eddy2).mean(axis=(1, 2))
    PZ = (1004.0/2.0) * (T_zm**2).mean(axis=(1, 2))
    PE = (1004.0/2.0) * T_eddy2.mean(axis=(1, 2))

    return KZ, KE, PZ, PE


u_data = ds.u.values
v_data = ds.v.values
T_data = ds.t.values

KZ, KE, PZ, PE = lorenz_energy_cycle_simple(
    u_data, v_data, T_data, lat, lev
)

print("KZ shape:", KZ.shape)
print("KE shape:", KE.shape)
print("PZ shape:", PZ.shape)
print("PE shape:", PE.shape)

# Total energy tendency
E_L = KZ + KE + PZ + PE
dE_L_dt = np.gradient(E_L) / (24 * 3600)

# Net Radiation Flux
Q = 340.0
alpha = 0.3
F = 240.0 + 10 * np.sin(2 * np.pi * np.arange(100) / 365)
R_n = Q * (1 - alpha) - F

# Energy Ratio gamma(t)
gamma = np.zeros_like(dE_L_dt)
R_n_safe = np.where(np.abs(R_n) < 1e-10, 1e-10, R_n)
gamma[1:] = dE_L_dt[1:] / R_n_safe[1:]
gamma[0] = gamma[1]

# Stochastic precipitation Z(t)
np.random.seed(42)
dt = 1.0
n_steps = len(time)
Z = np.zeros(n_steps)
Z[0] = 2.0

theta_Z = 0.1
mu_Z = 3.0 + 5.0 * gamma
sigma_Z = 1.5

for t in range(1, n_steps):
    dZ = (
        theta_Z * (mu_Z[t - 1] - Z[t - 1]) * dt
        + sigma_Z * np.sqrt(dt) * np.random.randn()
    )
    Z[t] = Z[t - 1] + dZ
    Z[t] = max(Z[t], 0)

corr = np.corrcoef(gamma, Z)[0, 1]

print("gamma min:", gamma.min())
print("gamma max:", gamma.max())
print("gamma mean:", gamma.mean())
print("gamma std:", gamma.std())
print("Z min:", Z.min())
print("Z max:", Z.max())
print("Z mean:", Z.mean())
print("Correlation between gamma and Z:", corr)
