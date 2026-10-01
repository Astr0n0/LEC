import runpy
import numpy as np

data = runpy.run_path("LEC_seeded.py")
gamma = data["gamma"]

base_mean = 3.0
coupling = 5
sigma = 0.0

thetas = [
    0.65,
    0.68,
    0.70,
    0.72,
    0.74,
    0.76,
    0.78,
    0.80,
]

print("theta      r0          r_lag1")

for theta in thetas:
    np.random.seed(42)

    z = np.zeros(len(gamma))
    z[0] = 2.0

    mu = base_mean + coupling * gamma

    for t in range(1, len(gamma)):
        dz = (
            theta * (mu[t - 1] - z[t - 1])
            + sigma * np.random.randn()
        )

        z[t] = max(z[t - 1] + dz, 0.0)

    r0 = np.corrcoef(gamma, z)[0, 1]
    r1 = np.corrcoef(gamma[:-1], z[1:])[0, 1]

    print(
        f"{theta:>5}    "
        f"{r0: .6f}    "
        f"{r1: .6f}"
    )
