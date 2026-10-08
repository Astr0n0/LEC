import numpy as np
import pandas as pd
from scipy.stats import spearmanr

RNG_SEED = 20261008
N_BOOT = 5000

cases = {
    "6-hourly": {
        "path": r"LEC_100d_real\analysis_timeseries.csv",
        "blocks": [4, 8, 12, 16],
    },
    "daily": {
        "path": r"LEC_100d_daily\analysis_timeseries.csv",
        "blocks": [2, 3, 4, 5, 7, 10],
    },
}


def moving_block_indices(n, block_size, rng):
    starts = np.arange(0, n - block_size + 1)
    needed = int(np.ceil(n / block_size))

    chosen = rng.choice(
        starts,
        size=needed,
        replace=True,
    )

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

    print(f"\n=== {name} ===")
    print(
        "block   pearson_low   pearson_high   "
        "spearman_low   spearman_high"
    )

    for block in cfg["blocks"]:
        rng = np.random.default_rng(RNG_SEED)

        p_boot = np.empty(N_BOOT)
        s_boot = np.empty(N_BOOT)

        for i in range(N_BOOT):
            idx = moving_block_indices(
                len(x),
                block,
                rng,
            )

            gb = gamma[idx]
            zb = z[idx]

            p_boot[i] = np.corrcoef(
                gb,
                zb,
            )[0, 1]

            s_boot[i] = spearmanr(
                gb,
                zb,
            ).statistic

        p_lo, p_hi = np.percentile(
            p_boot,
            [2.5, 97.5],
        )

        s_lo, s_hi = np.percentile(
            s_boot,
            [2.5, 97.5],
        )

        print(
            f"{block:>5} "
            f"{p_lo:>13.6f} "
            f"{p_hi:>14.6f} "
            f"{s_lo:>14.6f} "
            f"{s_hi:>15.6f}"
        )
