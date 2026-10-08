import io
import runpy
import numpy as np
from contextlib import redirect_stdout

results = []

for seed in range(100):
    np.random.seed(seed)

    with redirect_stdout(io.StringIO()):
        ns = runpy.run_path(
            "paper_appendix_reconstructed.py",
            run_name=f"__paper_seed_{seed}__",
        )

    gamma = ns["gamma"]
    Z = ns["Z"]
    r = np.corrcoef(gamma, Z)[0, 1]

    results.append((seed, r, gamma.std()))

r_values = np.array([x[1] for x in results])
gamma_std_values = np.array([x[2] for x in results])

best = max(results, key=lambda x: x[1])

print("runs:", len(results))
print("mean_r:", r_values.mean())
print("std_r:", r_values.std())
print("min_r:", r_values.min())
print("max_r:", r_values.max())
print("best_seed:", best[0])
print("best_r:", best[1])
print("q95_r:", np.percentile(r_values, 95))
print("q99_r:", np.percentile(r_values, 99))
print("count_r_ge_0.865:", np.sum(r_values >= 0.865))
print("gamma_std_mean:", gamma_std_values.mean())
print("gamma_std_min:", gamma_std_values.min())
print("gamma_std_max:", gamma_std_values.max())
