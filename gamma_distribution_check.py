"""Gamma distribution diagnostics using interval-aligned ERA5 inputs."""

from era5_analysis import load_interval_analysis

from analysis_config import get_analysis_inputs

LEC_FILE, RADIATION_FILE, PRECIPITATION_FILE = map(str, get_analysis_inputs())

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
