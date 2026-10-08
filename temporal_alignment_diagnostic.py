import numpy as np
import pandas as pd
from scipy.stats import spearmanr

LEC_FILE = r"era5_100d_fixed\paper_lec.csv"
RAD_FILE = "radiation_100d.csv"
PRECIP_FILE = "precipitation_100d.csv"

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

lec["E_L"] = lec[ENERGY_COLS].sum(axis=1)

seconds = (
    lec.index - lec.index[0]
).total_seconds().to_numpy(dtype=float)

lec["dELdt_centered"] = np.gradient(
    lec["E_L"].to_numpy(dtype=float),
    seconds,
)

dt_seconds = (
    lec.index.to_series().diff().dt.total_seconds()
)

lec["dELdt_interval"] = (
    lec["E_L"].diff() / dt_seconds
)

rn_col = "Rn" if "Rn" in rad.columns else "R_n"

df = (
    lec[
        [
            "E_L",
            "dELdt_centered",
            "dELdt_interval",
        ]
    ]
    .join(rad[[rn_col]], how="inner")
    .join(precip[["Z"]], how="inner")
    .dropna()
)

df = df.rename(columns={rn_col: "Rn"})

df["gamma_centered"] = (
    df["dELdt_centered"] / df["Rn"]
)

df["gamma_interval"] = (
    df["dELdt_interval"] / df["Rn"]
)

print("=== Temporal alignment diagnostic ===")
print("n:", len(df))
print("start:", df.index.min())
print("end:", df.index.max())

print()
print(
    "corr(dELdt_centered, dELdt_interval):",
    np.corrcoef(
        df["dELdt_centered"],
        df["dELdt_interval"],
    )[0, 1],
)

print()
print("=== All valid samples ===")

for name in [
    "gamma_centered",
    "gamma_interval",
]:
    pearson = np.corrcoef(
        df[name],
        df["Z"],
    )[0, 1]

    spearman = spearmanr(
        df[name],
        df["Z"],
    ).statistic

    print(
        name,
        "Pearson=",
        f"{pearson:.9f}",
        "Spearman=",
        f"{spearman:.9f}",
    )

print()
print(
    "corr(gamma_centered, gamma_interval):",
    np.corrcoef(
        df["gamma_centered"],
        df["gamma_interval"],
    )[0, 1],
)

print()
print("=== |Rn| threshold sensitivity ===")
print(
    "threshold   n   "
    "centered_P   interval_P   "
    "centered_S   interval_S"
)

for threshold in [0.5, 5, 10, 20, 30, 40, 50]:
    x = df.loc[
        np.abs(df["Rn"]) >= threshold
    ]

    cp = np.corrcoef(
        x["gamma_centered"],
        x["Z"],
    )[0, 1]

    ip = np.corrcoef(
        x["gamma_interval"],
        x["Z"],
    )[0, 1]

    cs = spearmanr(
        x["gamma_centered"],
        x["Z"],
    ).statistic

    is_ = spearmanr(
        x["gamma_interval"],
        x["Z"],
    ).statistic

    print(
        f"{threshold:>9.1f} "
        f"{len(x):>4} "
        f"{cp:>12.6f} "
        f"{ip:>12.6f} "
        f"{cs:>12.6f} "
        f"{is_:>12.6f}"
    )
