"""Autocorrelation diagnostics using interval-aligned ERA5 series."""

from era5_analysis import load_interval_analysis

LEC_FILE = r"era5_100d_fixed\paper_lec.csv"
RADIATION_FILE = "radiation_100d.csv"
PRECIPITATION_FILE = "precipitation_100d.csv"

for name, frequency, max_lag in (
    ("6-hourly", "6h", 20),
    ("Aligned daily", "D", 10),
):
    df = load_interval_analysis(
        LEC_FILE,
        RADIATION_FILE,
        PRECIPITATION_FILE,
        frequency=frequency,
        min_abs_rn=0.5,
    )

    print(f"\n=== {name} ===")
    for column in ["gamma", "Z"]:
        print(f"\n{column}")
        for lag in range(1, max_lag + 1):
            # pandas computes pairwise-complete autocorrelation without
            # deleting masked timestamps from the underlying timeline.
            value = df[column].autocorr(lag=lag)
            print(f"lag {lag:>2}: {value: .6f}")
