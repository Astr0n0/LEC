"""Large-|gamma| diagnostics using interval-aligned ERA5 inputs."""

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
    valid = df.dropna(subset=["gamma", "R_n", "dE_L_dt", "Z"]).copy()
    valid["abs_gamma"] = valid["gamma"].abs()
    valid["abs_Rn"] = valid["R_n"].abs()

    top = valid.nlargest(10, "abs_gamma")[
        ["gamma", "R_n", "dE_L_dt", "Z"]
    ]
    print(f"\n=== {name}: top |gamma| ===")
    print(top.to_string())
    print(
        "\ncorr(|gamma|, 1/|Rn|):",
        valid["abs_gamma"].corr(1.0 / valid["abs_Rn"]),
    )
