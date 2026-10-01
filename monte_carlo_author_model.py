import runpy
import numpy as np

data = runpy.run_path("LEC_seeded.py")
gamma = np.asarray(data["gamma"], dtype=float)

theta = 0.1
coupling = 5.0
sigma = 1.5
base_mean = 3.0

n_runs = 10000
rng = np.random.default_rng(12345)

correlations = np.empty(n_runs)

mu = base_mean + coupling * gamma

for run in range(n_runs):
    z = np.zeros(len(gamma))
    z[0] = 2.0

    noise = rng.standard_normal(len(gamma) - 1)

    for t in range(1, len(gamma)):
        dz = (
            theta * (mu[t - 1] - z[t - 1])
            + sigma * noise[t - 1]
        )
        z[t] = max(z[t - 1] + dz, 0.0)

    correlations[run] = np.corrcoef(gamma, z)[0, 1]

print("runs:", n_runs)
print("mean_r:", correlations.mean())
print("std_r:", correlations.std())
print("min_r:", correlations.min())
print("max_r:", correlations.max())
print("q95:", np.quantile(correlations, 0.95))
print("q99:", np.quantile(correlations, 0.99))
print("count_r_ge_0.865:", np.sum(correlations >= 0.865))
print("fraction_r_ge_0.865:", np.mean(correlations >= 0.865))
