import numpy as np
import pandas as pd

df = pd.read_csv(
    r".\LEC_100d_daily\analysis_timeseries.csv",
    parse_dates=["time"],
).set_index("time")

thresholds = [0.5, 5, 10, 20, 30, 40, 50]
lags = range(-10, 11)

results = []

for threshold in thresholds:
    gamma = df["gamma"].where(df["R_n"].abs() >= threshold)

    for lag in lags:
        x = pd.DataFrame(
            {
                "gamma": gamma,
                "Z": df["Z"].shift(-lag),
            }
        ).dropna()

        if len(x) > 2:
            r = x["gamma"].corr(x["Z"])
            results.append(
                (
                    abs(r),
                    threshold,
                    lag,
                    r,
                    len(x),
                )
            )

best = max(results)
observed = best[0]

null_distribution = []

for shift in range(1, len(df)):
    shifted_z = pd.Series(
        np.roll(df["Z"].to_numpy(), shift),
        index=df.index,
    )

    max_abs_r = 0.0

    for threshold in thresholds:
        gamma = df["gamma"].where(
            df["R_n"].abs() >= threshold
        )

        for lag in lags:
            x = pd.DataFrame(
                {
                    "gamma": gamma,
                    "Z": shifted_z.shift(-lag),
                }
            ).dropna()

            if len(x) > 2:
                r = abs(x["gamma"].corr(x["Z"]))
                max_abs_r = max(max_abs_r, r)

    null_distribution.append(max_abs_r)

p_corrected = (
    1
    + sum(value >= observed for value in null_distribution)
) / (1 + len(null_distribution))

print("BEST OBSERVED:")
print(
    f"threshold={best[1]} "
    f"lag={best[2]} "
    f"n={best[4]} "
    f"r={best[3]:.6f}"
)

print(
    f"circular_shift_corrected_p={p_corrected:.6f}"
)

print(
    f"null_95pct="
    f"{np.percentile(null_distribution, 95):.6f}"
)