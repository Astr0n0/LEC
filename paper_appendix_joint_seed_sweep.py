import io
import runpy
import numpy as np
from contextlib import redirect_stdout

theta = 0.1
coupling = 5.0
sigma = 1.5
base_mean = 3.0

atmospheric_seeds = range(100)
precipitation_seeds = range(100)

results = []

for atm_seed in atmospheric_seeds:
    np.random.seed(atm_seed)

    with redirect_stdout(io.StringIO()):
        ns = runpy.run_path(
            "paper_appendix_reconstructed.py",
            run_name=f"__atm_seed_{atm_seed}__",
        )

    gamma = np.asarray(ns["gamma"], dtype=float)
    mu = base_mean + coupling * gamma

    for precip_seed in precipitation_seeds:
        rng = np.random.RandomState(precip_seed)

        z = np.zeros(len(gamma))
        z[0] = 2.0

        for t in range(1, len(gamma)):
            dz = (
                theta * (mu[t - 1] - z[t - 1])
                + sigma * rng.randn()
            )
            z[t] = max(z[t - 1] + dz, 0.0)

        r = np.corrcoef(gamma, z)[0, 1]
        results.append((atm_seed, precip_seed, r))

r_values = np.array([x[2] for x in results])
best = max(results, key=lambda x: x[2])

print("runs:", len(results))
print("mean_r:", r_values.mean())
print("std_r:", r_values.std())
print("min_r:", r_values.min())
print("max_r:", r_values.max())
print("best_atmospheric_seed:", best[0])
print("best_precipitation_seed:", best[1])
print("best_r:", best[2])
print("q95_r:", np.percentile(r_values, 95))
print("q99_r:", np.percentile(r_values, 99))
print("q999_r:", np.percentile(r_values, 99.9))
print("count_r_ge_0.865:", np.sum(r_values >= 0.865))
print("fraction_r_ge_0.865:", np.mean(r_values >= 0.865))
