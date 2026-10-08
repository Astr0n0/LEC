import io
import runpy
import numpy as np
from contextlib import redirect_stdout

with redirect_stdout(io.StringIO()):
    data = runpy.run_path("LEC_seeded.py")

gamma = np.asarray(data["gamma"], dtype=float)

theta = 0.1
coupling = 5.0
sigma = 1.5
base_mean = 3.0
mu = base_mean + coupling * gamma

n_runs = 10000
correlations = np.empty(n_runs)

for seed in range(n_runs):
    rng = np.random.RandomState(seed)

    z = np.zeros(len(gamma))
    z[0] = 2.0

    for t in range(1, len(gamma)):
        dz = (
            theta * (mu[t - 1] - z[t - 1])
            + sigma * rng.randn()
        )
        z[t] = max(z[t - 1] + dz, 0.0)

    correlations[seed] = np.corrcoef(gamma, z)[0, 1]

best_seed = int(np.argmax(correlations))

print("runs:", n_runs)
print("mean_r:", correlations.mean())
print("std_r:", correlations.std())
print("min_r:", correlations.min())
print("max_r:", correlations.max())
print("best_seed:", best_seed)
print("best_r:", correlations[best_seed])
print("q95_r:", np.percentile(correlations, 95))
print("q99_r:", np.percentile(correlations, 99))
print("count_r_ge_0.865:", np.sum(correlations >= 0.865))
print("fraction_r_ge_0.865:", np.mean(correlations >= 0.865))
