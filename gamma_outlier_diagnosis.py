"""Large-|gamma| diagnostics using interval-aligned ERA5 inputs."""

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
