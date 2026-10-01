import contextlib
import gc
import io
import runpy
import warnings

import matplotlib.pyplot as plt
import numpy as np

warnings.filterwarnings("ignore")

# Prevent LEC.py from writing/showing figures during repeated runs.
plt.savefig = lambda *args, **kwargs: None
plt.show = lambda *args, **kwargs: None

n_runs = 100
correlations = np.empty(n_runs)

for seed in range(n_runs):
    np.random.seed(seed)

    with contextlib.redirect_stdout(io.StringIO()):
        data = runpy.run_path("LEC.py")

    gamma = np.asarray(data["gamma"], dtype=float)
    z = np.asarray(data["Z"], dtype=float)

    correlations[seed] = np.corrcoef(gamma, z)[0, 1]

    plt.close("all")
    del data, gamma, z
    gc.collect()

    if (seed + 1) % 10 == 0:
        print(f"completed: {seed + 1}/{n_runs}")

best_seed = int(np.nanargmax(correlations))

print()
print("runs:", n_runs)
print("mean_r:", np.nanmean(correlations))
print("std_r:", np.nanstd(correlations))
print("min_r:", np.nanmin(correlations))
print("max_r:", np.nanmax(correlations))
print("best_seed:", best_seed)
print("q95:", np.nanquantile(correlations, 0.95))
print("q99:", np.nanquantile(correlations, 0.99))
print("count_r_ge_0.865:", np.sum(correlations >= 0.865))