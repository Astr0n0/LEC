# Requires: xarray, numpy, matplotlib, scipy, scikit-learn
#=====================================================================

import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde
import xarray as xr
# Note: lec package import commented as it's not standard
# from lec import LorenzEnergyCycle  # <-- From GitHub package

# -------------------------------
# 1. Load or generate synthetic data
# -------------------------------
# For demo: generate synthetic wind/temperature fields
lon = np.linspace(0, 360, 72)
lat = np.linspace(-90, 90, 36)
lev = np.array([1000, 850, 700, 500, 300, 200, 100])  # hPa

# FIXED: Use regular datetime instead of cftime for simpler plotting
time = xr.date_range(start="2020-01-01", periods=100, freq="D")  # Removed use_cftime=True

# Create properly shaped synthetic data using vectorized operations
time_coord = np.arange(100)
lat_rad = np.deg2rad(lat)

# Vectorized array creation for better performance
u = (20 * np.cos(lat_rad)[np.newaxis, :, np.newaxis, np.newaxis] * 
     np.sin(2 * np.pi * time_coord[:, np.newaxis, np.newaxis, np.newaxis] / 365) + 
     2 * np.random.randn(100, 36, 72, 7))

v = (5 * np.sin(lat_rad)[np.newaxis, :, np.newaxis, np.newaxis] * 
     np.ones((100, 36, 72, 7)) + 
     1 * np.random.randn(100, 36, 72, 7))

T = (288 - 60 * np.cos(lat_rad)[np.newaxis, :, np.newaxis, np.newaxis] - 
     0.006 * lev[np.newaxis, np.newaxis, np.newaxis, :] + 
     2 * np.random.randn(100, 36, 72, 7))

ds = xr.Dataset(
    {
        "u": (["time", "lat", "lon", "lev"], u),
        "v": (["time", "lat", "lon", "lev"], v),
        "t": (["time", "lat", "lon", "lev"], T)
    },
    coords={
        "time": time, 
        "lat": lat, 
        "lon": lon, 
        "lev": lev
    }
)

print("Dataset created successfully!")
# FIXED: Use ds.sizes instead of ds.dims to avoid FutureWarning
print(f"Dataset dimensions: {dict(ds.sizes)}")
print(f"Variable shapes: u{ds.u.shape}, v{ds.v.shape}, t{ds.t.shape}")

# -------------------------------
# 2. Compute LEC using custom function (since lec package not standard)
# -------------------------------
def lorenz_energy_cycle_simple(u, v, T, lat, lev):
    """
    Simplified LEC computation for demonstration
    """
    # Zonal means
    u_zm = u.mean(axis=2)  # Average over longitude
    v_zm = v.mean(axis=2)  # Average over longitude
    T_zm = T.mean(axis=2)  # Average over longitude
    
    # Eddy variances
    u_eddy2 = ((u - u_zm[:, :, np.newaxis, :])**2).mean(axis=2)
    v_eddy2 = ((v - v_zm[:, :, np.newaxis, :])**2).mean(axis=2)
    T_eddy2 = ((T - T_zm[:, :, np.newaxis, :])**2).mean(axis=2)
    
    # Simple energy calculations (placeholder)
    KZ = 0.5 * (u_zm**2 + v_zm**2).mean(axis=(1, 2))  # Mean over lat, lev
    KE = 0.5 * (u_eddy2 + v_eddy2).mean(axis=(1, 2))  # Mean over lat, lev
    PZ = (1004.0/2.0) * (T_zm**2).mean(axis=(1, 2))   # Mean over lat, lev
    PE = (1004.0/2.0) * T_eddy2.mean(axis=(1, 2))     # Mean over lat, lev
    
    return KZ, KE, PZ, PE

# Extract data from dataset
u_data = ds.u.values
v_data = ds.v.values  
T_data = ds.t.values

KZ, KE, PZ, PE = lorenz_energy_cycle_simple(u_data, v_data, T_data, lat, lev)

# Total energy tendency
E_L = KZ + KE + PZ + PE
dE_L_dt = np.gradient(E_L) / (24*3600)  # Convert daily to s

# -------------------------------
# 3. Net Radiation Flux (NRF)
# -------------------------------
Q = 340.0  # Global mean incoming SW (W/m^2)
alpha = 0.3  # Planetary albedo
F = 240.0 + 10 * np.sin(2*np.pi*np.arange(100)/365)  # OLR variation
R_n = Q * (1 - alpha) - F  # Net radiation flux (W/m^2)

# -------------------------------
# 4. Energy Ratio gamma(t)
# -------------------------------
gamma = np.zeros_like(dE_L_dt)
# Avoid division by zero
R_n_safe = np.where(np.abs(R_n) < 1e-10, 1e-10, R_n)
gamma[1:] = dE_L_dt[1:] / R_n_safe[1:]
gamma[0] = gamma[1]  # Fill first value

# -------------------------------
# 5. Simulate Precipitation Z(t) stochastically
# -------------------------------
# Ornstein-Uhlenbeck (mean-reverting) process for Z(t) influenced by gamma
np.random.seed(42)
dt = 1.0
n_steps = len(time)
Z = np.zeros(n_steps)
Z[0] = 2.0

theta_Z = 0.1
mu_Z = 3.0 + 5.0 * gamma  # Mean precipitation depends on gamma
sigma_Z = 1.5

for t in range(1, n_steps):
    dZ = theta_Z * (mu_Z[t-1] - Z[t-1]) * dt + sigma_Z * np.sqrt(dt) * np.random.randn()
    Z[t] = Z[t-1] + dZ
    Z[t] = max(Z[t], 0)  # Precipitation >= 0

# -------------------------------
# 6. Estimate Conditional PDF P(Z|gamma)
# -------------------------------
# Use Kernel Density Estimation
# Filter out extreme values
valid_idx = (gamma > np.percentile(gamma, 1)) & (gamma < np.percentile(gamma, 99))
gamma_filtered = gamma[valid_idx]
Z_filtered = Z[valid_idx]

if len(gamma_filtered) > 10:
    try:
        kde = gaussian_kde(np.vstack([gamma_filtered, Z_filtered]))
        Z_grid = np.linspace(0, 20, 100)
        gamma_grid = np.linspace(gamma_filtered.min(), gamma_filtered.max(), 50)
        Gamma_mesh, Z_mesh = np.meshgrid(gamma_grid, Z_grid)
        positions = np.vstack([Gamma_mesh.ravel(), Z_mesh.ravel()])
        joint_pdf = kde(positions).reshape(Z_grid.size, gamma_grid.size)

        # Marginal P(gamma)
        # FIXED: Use np.trapezoid instead of deprecated np.trapz
        P_gamma = np.trapezoid(joint_pdf, Z_grid, axis=0)
        P_gamma[P_gamma == 0] = 1e-12

        # Conditional P(Z|gamma)
        P_Z_given_gamma = joint_pdf / P_gamma[np.newaxis, :]

        # PDF Ratio Psi(Z, gamma)
        Psi = P_Z_given_gamma / P_gamma[np.newaxis, :]
    except Exception as e:
        print(f"KDE computation failed: {e}")
        # Fallback values
        Z_grid = np.linspace(0, 20, 100)
        gamma_grid = np.linspace(gamma.min(), gamma.max(), 50)
        P_Z_given_gamma = np.zeros((len(Z_grid), len(gamma_grid)))
        Psi = np.zeros((len(Z_grid), len(gamma_grid)))
else:
    print("Insufficient data for KDE")
    # Fallback values
    Z_grid = np.linspace(0, 20, 100)
    gamma_grid = np.linspace(gamma.min(), gamma.max(), 50)
    P_Z_given_gamma = np.zeros((len(Z_grid), len(gamma_grid)))
    Psi = np.zeros((len(Z_grid), len(gamma_grid)))

# -------------------------------
# 7. Create and save individual figures
# -------------------------------
# FIXED: Convert time to numpy datetime64 for plotting
time_np = time.to_numpy()

# Set consistent style for all figures
plt.style.use('default')
plt.rcParams.update({'font.size': 10, 'figure.dpi': 300})

# Figure 1: Time series
plt.figure(figsize=(8, 5))
plt.plot(time_np, Z, label='Precipitation Z(t) [mm/day]', linewidth=1.5)
plt.plot(time_np, gamma, label=r'Energy ratio $\gamma(t)$', alpha=0.8, linewidth=1.5)
plt.legend()
plt.title('Time Evolution of Precipitation and Energy Ratio')
plt.xlabel('Date')
plt.ylabel('Value')
plt.xticks(rotation=45)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('time_series_plot.png', dpi=300, bbox_inches='tight')
plt.close()
print("Saved: time_series_plot.png")

# Figure 2: Scatter plot
plt.figure(figsize=(6, 5))
plt.scatter(gamma, Z, alpha=0.6, s=15, c='blue', edgecolors='none')
plt.xlabel(r'Energy ratio $\gamma(t)$')
plt.ylabel('Precipitation Z(t) [mm/day]')
plt.title('Scatter Plot: Z vs $\\gamma$')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('scatter_plot.png', dpi=300, bbox_inches='tight')
plt.close()
print("Saved: scatter_plot.png")

# Figure 3: Conditional PDF
plt.figure(figsize=(7, 5))
if len(gamma_filtered) > 10:
    try:
        im = plt.contourf(gamma_grid, Z_grid, P_Z_given_gamma, cmap='Blues', levels=20)
        plt.colorbar(im, label=r'Conditional PDF $P(Z|\gamma)$')
        plt.xlabel(r'Energy ratio $\gamma$')
        plt.ylabel('Precipitation Z [mm/day]')
        plt.title('Conditional PDF $P(Z|\\gamma)$')
        plt.tight_layout()
        plt.savefig('conditional_pdf.png', dpi=300, bbox_inches='tight')
        plt.close()
        print("Saved: conditional_pdf.png")
    except Exception as e:
        print(f"Failed to save conditional_pdf.png: {e}")
else:
    print("Skipped: conditional_pdf.png (insufficient data)")

# Figure 4: PDF Ratio Psi
plt.figure(figsize=(7, 5))
if len(gamma_filtered) > 10:
    try:
        Psi_clean = np.nan_to_num(Psi, nan=0.0, posinf=0.0, neginf=0.0)
        # Normalize for better visualization
        Psi_clean = Psi_clean / np.max(Psi_clean) if np.max(Psi_clean) > 0 else Psi_clean
        im2 = plt.contourf(gamma_grid, Z_grid, Psi_clean, cmap='Reds', levels=20)
        plt.colorbar(im2, label=r'PDF Ratio $\Psi(Z,\gamma)$')
        plt.xlabel(r'Energy ratio $\gamma$')
        plt.ylabel('Precipitation Z [mm/day]')
        plt.title('PDF Ratio $\\Psi(Z,\\gamma)$')
        plt.tight_layout()
        plt.savefig('pdf_ratio.png', dpi=300, bbox_inches='tight')
        plt.close()
        print("Saved: pdf_ratio.png")
    except Exception as e:
        print(f"Failed to save pdf_ratio.png: {e}")
else:
    print("Skipped: pdf_ratio.png (insufficient data)")

# -------------------------------
# 8. Statistical Validation and Figure 5
# -------------------------------
if len(gamma) > 5:
    try:
        corr = np.corrcoef(gamma, Z)[0,1]
        print(f"Correlation between gamma and Z: {corr:.3f}")

        # Figure 5: Conditional mean E[Z|gamma]
        gamma_bins = np.linspace(gamma.min(), gamma.max(), 15)
        Z_cond_mean = []
        gamma_bin_centers = []
        for i in range(len(gamma_bins)-1):
            mask = (gamma >= gamma_bins[i]) & (gamma < gamma_bins[i+1])
            if np.sum(mask) > 0:
                Z_cond_mean.append(np.mean(Z[mask]))
                gamma_bin_centers.append((gamma_bins[i] + gamma_bins[i+1]) / 2)
        
        if Z_cond_mean:  # Check if list is not empty
            Z_cond_mean = np.array(Z_cond_mean)
            plt.figure(figsize=(7, 5))
            plt.plot(gamma_bin_centers, Z_cond_mean, 'o-', label=r'Conditional mean $E[Z|\gamma]$', 
                    markersize=6, linewidth=2)
            plt.xlabel(r'Energy ratio $\gamma$')
            plt.ylabel('Mean Precipitation [mm/day]')
            plt.title('Conditional Expectation $E[Z|\\gamma]$')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig('conditional_expectation.png', dpi=300, bbox_inches='tight')
            plt.close()
            print("Saved: conditional_expectation.png")
        else:
            print("No valid bins for conditional expectation plot")
            
    except Exception as e:
        print(f"Statistical analysis failed: {e}")
else:
    print("Insufficient data for correlation analysis")

print("\nAll figures saved individually!")
print("Figure files created:")
print("- time_series_plot.png")
print("- scatter_plot.png") 
print("- conditional_pdf.png")
print("- pdf_ratio.png")
print("- conditional_expectation.png")
print("\nScript completed successfully!")
