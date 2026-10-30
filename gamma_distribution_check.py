"""Gamma distribution diagnostics using interval-aligned ERA5 inputs."""

from era5_analysis import load_interval_analysis

LEC_FILE = r"era5_100d_fixed\paper_lec.csv"
RADIATION_FILE = "radiation_100d.csv"
PRECIPITATION_FILE = "precipitation_100d.csv"

for name, frequency in (("6-hourly", "6h"), ("Aligned daily", "D")):
    df = load_interval_analysis(
        LEC_FILE,
        RADIATION_FILE,
        PRECIPITATION_FILE,
        frequency=frequency,
        min_abs_rn=0.5,
    )
    gamma = df["gamma"].dropna()

    print(f"\n=== {name} ===")
    print(gamma.describe(
        percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
    ).to_string())
    print("max_abs_gamma:", gamma.abs().max())
