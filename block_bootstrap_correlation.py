import numpy as np
import pandas as pd
from scipy.stats import spearmanr

RNG_SEED = 20261008
N_BOOT = 10000

cases = {
    "6-hourly": {
        "path": r"LEC_100d_real\analysis_timeseries.csv",
        "block": 8,
    },
    "daily": {
        "path": r"LEC_100d_daily\analysis_timeseries.csv",
        "block": 2,
    },
}


def moving_block_indices(n, block_size, rng):
    starts = np.arange(0, n - block_size + 1)
    needed = int(np.ceil(n / block_size))

    chosen = rng.choice(starts, size=needed, replace=True)

    idx = np.concatenate([
        np.arange(start, start + block_size)
        for start in chosen
    ])

    return idx[:n]


for name, cfg in cases.items():
    df = pd.read_csv(cfg["path"])

    x = df[["gamma", "Z"]].replace(
        [np.inf, -np.inf], np.nan
    ).dropna().reset_index(drop=True)

    gamma = x["gamma"].to_numpy(float)
    z = x["Z"].to_numpy(float)

    n = len(x)
    block = cfg["block"]

    observed_pearson = np.corrcoef(gamma, z)[0, 1]
    observed_spearman = spearmanr(gamma, z).statistic

    rng = np.random.default_rng(RNG_SEED)

    pearson_boot = np.empty(N_BOOT)
    spearman_boot = np.empty(N_BOOT)

    for i in range(N_BOOT):
        idx = moving_block_indices(n, block, rng)

        gb = gamma[idx]
        zb = z[idx]

        pearson_boot[i] = np.corrcoef(gb, zb)[0, 1]
        spearman_boot[i] = spearmanr(gb, zb).statistic

    p_lo, p_hi = np.percentile(
        pearson_boot, [2.5, 97.5]
    )

    s_lo, s_hi = np.percentile(
        spearman_boot, [2.5, 97.5]
    )

    print(f"\n=== {name} ===")
    print("n:", n)
    print("block_size:", block)
    print("bootstrap_runs:", N_BOOT)

    print(
        "pearson_observed:",
        f"{observed_pearson:.6f}",
    )
    print(
        "pearson_95pct_CI:",
        f"[{p_lo:.6f}, {p_hi:.6f}]",
    )

    print(
        "spearman_observed:",
        f"{observed_spearman:.6f}",
    )
    print(
        "spearman_95pct_CI:",
        f"[{s_lo:.6f}, {s_hi:.6f}]",
    )
