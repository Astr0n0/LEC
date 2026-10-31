"""Resolve the active LEC analysis inputs without editing script paths."""

from __future__ import annotations

from pathlib import Path


def get_analysis_inputs(project_root: str | Path = ".") -> tuple[Path, Path, Path]:
    """Prefer the extended, 100-complete-day data set when it is available."""
    root = Path(project_root).expanduser().resolve()
    candidates = [
        (
            root / "era5_100d_extended_fixed" / "paper_lec.csv",
            root / "radiation_100d_extended.csv",
            root / "precipitation_100d_extended.csv",
        ),
        (
            root / "era5_100d_fixed" / "paper_lec.csv",
            root / "radiation_100d.csv",
            root / "precipitation_100d.csv",
        ),
    ]
    for paths in candidates:
        if all(path.is_file() for path in paths):
            return paths
    expected = "\n".join("  " + " | ".join(str(p) for p in group) for group in candidates)
    raise FileNotFoundError(
        "No complete LEC/radiation/precipitation input set was found. "
        "Expected one of these complete sets:\n" + expected
    )


def get_analysis_timeseries_path(project_root: str | Path = ".") -> Path:
    """Prefer the extended interval analysis, then the legacy real-data output."""
    root = Path(project_root).expanduser().resolve()
    candidates = [
        root / "LEC_100d_extended_analysis" / "analysis_timeseries.csv",
        root / "LEC_100d_real" / "analysis_timeseries.csv",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "No analysis_timeseries.csv found in the extended or legacy analysis folder."
    )
