# Reproducibility and delivery guide

## Required input files
The repository contains code and documentation, not the private ERA5 NetCDF files. Place these files in the repository root:
- era5_100d.nc — pressure-level data, 400 states at six-hour cadence.
- era5_surface_100d.nc — surface data, 2400 hourly records.

The endpoint extension validates exact timestamps and variable names. Do not rename variables manually to bypass validation.

## CDS API credentials
The endpoint-extension step uses the Copernicus Climate Data Store API. Configure CDS API credentials for an account with ERA5 access, following current CDS API instructions for the installed cdsapi version. Never commit the credentials file or paste an API key into source code, logs, issues or pull requests.

## One-command run
From the project root, with the Python environment active:

    python run_era5_pipeline.py

The pipeline:
1. Runs deterministic unit tests.
2. Fetches only the missing pressure-level and surface endpoints at 2020-04-10 00 UTC if extended files are absent.
3. Validates the 401 pressure-level and 2401 hourly surface timestamps.
4. Processes 400 complete six-hour surface intervals.
5. Runs LorenzCycleToolkit if the validated 401-state Toolkit CSV is absent.
6. Validates all four energy reservoirs and exact time coordinates.
7. Produces 400 six-hourly and 100 complete daily analysis rows.
8. Runs optional statistical and regional diagnostics.
9. Writes a manifest and individual diagnostic logs.

Original NetCDF files are not modified. Extended files and derived outputs are written separately. Existing outputs that fail validation are not silently overwritten. Use --skip-diagnostics to omit optional sensitivity/bootstrap scripts, or --min-abs-rn VALUE to change the gamma denominator mask threshold; record that choice in reports.

## Expected outputs

Extended raw data: era5_100d_extended.nc, era5_surface_100d_extended.nc, era5_pressure_endpoint_2020-04-10.nc and era5_surface_endpoint_2020-04-10.nc.

Processed surface data: radiation_100d_extended.csv and precipitation_100d_extended.csv.

Toolkit output: era5_100d_extended_fixed/paper_lec.csv.

Analysis folders: LEC_100d_extended_analysis and LEC_100d_extended_daily_analysis. Each contains analysis_timeseries.csv, summary.csv, conditional_pdf.csv, psi.csv, conditional_cdf.csv, precipitation_exceedance_probability.csv, precipitation_exceedance_timeseries.csv, analysis_metadata.json and plots. The six-hourly folder also contains pipeline_manifest.json and pipeline_logs/.

## Validation criteria
- 401 unique six-hourly pressure states from 2020-01-01 00 to 2020-04-10 00 UTC.
- 2401 unique hourly surface timestamps over the same endpoint range.
- 400 complete six-hour surface intervals ending 2020-01-01 06 through 2020-04-10 00 UTC.
- Exact timestamp agreement among LEC tendency, radiation and precipitation.
- 400 six-hourly and 100 complete daily analysis rows.
- No missing or non-finite energy reservoirs in validated Toolkit output.
- A manifest recording package versions, Git commit, inputs, sample counts, threshold and diagnostic outcomes.

GitHub Actions tests validate code-level behavior only. They do not download ERA5, validate the local CDS account or prove the Toolkit succeeds on the user's NetCDF files.

## Reporting results
Report sample sizes, interval, spatial domain, units, denominator threshold, correlation type, uncertainty interval and diagnostic method. Keep six-hourly and daily results distinct. Never cite the paper's synthetic r=0.865 as an ERA5 result.

Do not describe the project as complete until the local end-to-end run has passed the validation criteria and its manifest and logs have been reviewed.