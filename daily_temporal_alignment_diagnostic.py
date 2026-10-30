import numpy as np
import pandas as pd
from scipy.stats import spearmanr

LEC_FILE = r"era5_100d_fixed\paper_lec.csv"
RAD_FILE = "radiation_100d.csv"
PRECIP_FILE = "precipitation_100d.csv"
CURRENT_DAILY_FILE = r"LEC_100d_daily\analysis_timeseries.csv"

ENERGY_COLS = ["Az", "Ae", "Kz", "Ke"]


def read_time_csv(path):
    df = pd.read_csv(path)

    candidates = [
        c for c in df.columns
        if c.lower() in {
            "time",
            "valid_time",
            "date",
            "datetime",
            "timestamp",
        }
    ]

    time_col = candidates[0] if candidates else df.columns[0]
    idx = pd.to_datetime(df[time_col], errors="raise")

    df = df.drop(columns=[time_col])
    df.index = pd.DatetimeIndex(idx, name="time")

    return df.sort_index()


lec = read_time_csv(LEC_FILE)
rad = read_time_csv(RAD_FILE)
precip = read_time_csv(PRECIP_FILE)
current_daily = read_time_csv(CURRENT_DAILY_FILE)

lec["E_L"] = lec[ENERGY_COLS].sum(axis=1)

dt_seconds = (
    lec.index.to_series()
    .diff()
    .dt.total_seconds()
)

lec["dELdt_interval"] = (
    lec["E_L"].diff() / dt_seconds
)

seconds = (
    lec.index - lec.index[0]
).total_seconds().to_numpy(dtype=float)

lec["dELdt_centered"] = np.gradient(
    lec["E_L"].to_numpy(dtype=float),
    seconds,
)

rn_col = "Rn" if "Rn" in rad.columns else "R_n"

sixh = (
    lec[
        [
            "dELdt_interval",
            "dELdt_centered",
        ]
    ]
    .join(rad[[rn_col]], how="inner")
    .join(precip[["Z"]], how="inner")
    .dropna()
    .rename(columns={rn_col: "Rn"})
)

# Each right-labelled 6-hour sample represents the interval ending
# at its timestamp. Four samples in (day 00 UTC, next day 00 UTC]
# therefore form one complete 24-hour period.
daily_counts = sixh["Rn"].resample(
    "24h",
    origin="start_day",
    closed="right",
    label="right",
).count()

daily = sixh.resample(
    "24h",
    origin="start_day",
    closed="right",
    label="right",
).mean()

daily = daily.loc[daily_counts == 4].copy()

daily["gamma_interval"] = (
    daily["dELdt_interval"] / daily["Rn"]
)

daily["gamma_centered"] = (
    daily["dELdt_centered"] / daily["Rn"]
)

print("=== Complete 24-hour windows ===")
print("n:", len(daily))
print("first_label:", daily.index.min())
print("last_label:", daily.index.max())

print()
print("=== Correctly aligned daily correlations ===")

for name in [
    "gamma_interval",
    "gamma_centered",
]:
    p = np.corrcoef(
        daily[name],
        daily["Z"],
    )[0, 1]

    s = spearmanr(
        daily[name],
        daily["Z"],
    ).statistic

    print(
        name,
        "Pearson=",
        f"{p:.9f}",
        "Spearman=",
        f"{s:.9f}",
    )

print()
print("=== Current saved daily analysis ===")

current = current_daily[
    ["gamma", "Z"]
].replace(
    [np.inf, -np.inf],
    np.nan,
).dropna()

print("n:", len(current))

print(
    "Pearson=",
    f"{np.corrcoef(current['gamma'], current['Z'])[0,1]:.9f}",
)

print(
    "Spearman=",
    f"{spearmanr(current['gamma'], current['Z']).statistic:.9f}",
)

print()
print("=== |Rn| threshold sensitivity: aligned interval daily ===")
print("threshold   n   Pearson   Spearman")

for threshold in [0.5, 5, 10, 20, 30, 40, 50]:
    x = daily.loc[
        np.abs(daily["Rn"]) >= threshold
    ]

    p = np.corrcoef(
        x["gamma_interval"],
        x["Z"],
    )[0, 1]

    s = spearmanr(
        x["gamma_interval"],
        x["Z"],
    ).statistic

    print(
        f"{threshold:>9.1f} "
        f"{len(x):>4} "
        f"{p:>9.6f} "
        f"{s:>10.6f}"
    )
