# Contributing and quality checks

## Development branch
Use a feature branch for changes. Do not commit directly to main unless repository maintainers explicitly request it.

## Environment
Target Python version is 3.13. Dependency constraints are in requirements.txt.

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt

If PowerShell blocks activation, invoke .venv\Scripts\python.exe directly or use an approved execution-policy procedure. Do not weaken a machine-wide execution policy solely for this project.

## Tests
Run from the repository root:

    python -m compileall -q analysis_config.py era5_metadata.py era5_surface_processing.py temporal_validation.py era5_analysis.py LEC_reproduction.py prepare_era5_surface.py extend_era5_100d.py run_era5_pipeline.py
    python -m unittest discover -v

Tests must not require CDS credentials or download ERA5 data. Keep network retrieval and real-data integration checks separate from deterministic unit tests.

## Scientific changes
For changes to time aggregation, units, variable conventions, energy reservoirs or probability calculations:
1. Update the relevant scientific documentation.
2. Add a deterministic regression test.
3. Preserve original source data and write transformed data to new outputs.
4. Record the data interval, units, assumptions and validation counts.
5. Do not describe a result as final until the full real-data pipeline has run.

## Pull requests
State the scientific reason for the change, list affected files, report test results, and distinguish unit-test validation from real-data validation. Never commit API keys, CDS credentials, private data or large raw ERA5 NetCDF files.