# LEC paper reproduction — corrected implementation

This folder replaces the placeholder LEC calculation in the supplied `LEC.py` with diagnostics produced by **daniloceano/LorenzCycleToolkit**.

## ERA5 accumulation convention and complete 100-day coverage

The current single-level request is for hourly ERA5 **reanalysis**. ECMWF
specifies that hourly **tp**, **tsr** and **ttr** values are one-hour
accumulations ending at each validity timestamp. They are summed over six
hours; consecutive values are not differenced. The official verification,
units, sign convention and time-coverage audit are documented in
[ERA5_TEMPORAL_VALIDATION.md](ERA5_TEMPORAL_VALIDATION.md).

The original files provide 399 complete six-hour surface intervals and
therefore 99 complete right-closed daily windows. To obtain exactly 100
complete days, run the following from the project root to fetch only the
missing 2020-04-10 00:00 UTC pressure-level and surface endpoints:

    python extend_era5_100d.py

The script writes separate extended NetCDF files and never modifies the
originals. Then run:

    python prepare_era5_surface.py --input-file era5_surface_100d_extended.nc --radiation-output radiation_100d_extended.csv --precipitation-output precipitation_100d_extended.csv


## What changed

The old code estimated `KZ`, `KE`, `PZ`, and `PE` with simple grid variances and temperature squares. Those quantities are not a complete Lorenz Energy Cycle diagnostic. The rewritten workflow uses LorenzCycleToolkit reservoirs:

- `Az`: zonal available potential energy
- `Ae`: eddy available potential energy
- `Kz`: zonal kinetic energy
- `Ke`: eddy kinetic energy

LorenzCycleToolkit stores these reservoirs in **J m⁻²**. We therefore calculate

`E_L = Az + Ae + Kz + Ke`

and use the actual timestamps to obtain

`dE_L/dt` in **W m⁻²**. Because ERA5 accumulated radiation and precipitation
at timestamp `t` describe the interval ending at `t`, the primary tendency is
the matching interval difference
`[E_L(t) - E_L(t-6h)] / 6h`. The centered derivative is retained only as a
diagnostic and is not used in `gamma`.

The paper's first definition of the energy ratio is then implemented directly:

`gamma(t) = [dE_L/dt] / R_n(t)`

so `gamma` is dimensionless when `R_n` is supplied in W m⁻².

## Important scientific decision

For standard ERA5 data, LorenzCycleToolkit's direct `Dz`/`De` dissipation pathway cannot normally be used because the required friction-force components are not present. The toolkit's residual mode provides `RKz`/`RKe`, but those residuals include more than physical frictional dissipation (boundary pressure work, unresolved-scale transfer, and numerical error). Therefore this implementation **does not pretend that `RKz` and `RKe` are the paper's `Dz` and `De`**.

Instead, it uses the directly diagnosed total reservoir tendency `dE_L/dt`, which corresponds to the first equality in the paper's gamma definition. If the authors later require an explicit `Gz + Ge - Dz - De` decomposition, the atmospheric dataset and domain must support that decomposition physically; this needs a separate methodological decision rather than a code shortcut.

## Toolkit input expected for modern ERA5/Copernicus pressure-level files

The built-in default namelist expects:

- `t` — temperature [K]
- `z` — geopotential [m² s⁻²]
- `w` — pressure vertical velocity [Pa s⁻¹]
- `u` — eastward wind [m s⁻¹]
- `v` — northward wind [m s⁻¹]
- coordinates: `longitude`, `latitude`, `valid_time`, `pressure_level`

A custom namelist can be supplied if the NetCDF uses different variable names.

## Recommended workflow

### 1. Install

Use Python 3.13.3 (the tested environment) and install `requirements.txt`.

### 2. Run LorenzCycleToolkit and the paper analysis in one command

```bash
python LEC_reproduction.py \
  --atmospheric-nc era5_pressure_levels.nc \
  --domain -60 -30 -42.5 -17.5 \
  --radiation-csv radiation.csv \
  --precipitation-csv precipitation.csv \
  --output-dir results
```

The script invokes LorenzCycleToolkit in fixed-domain residual mode. Residual mode is used only to make the standard ERA5 Toolkit run valid; gamma itself is calculated from `dE_L/dt`, not from residual dissipation terms.

### 3. Reuse an already generated Toolkit CSV

```bash
python LEC_reproduction.py \
  --lec-results paper_lec.csv \
  --radiation-csv radiation.csv \
  --precipitation-csv precipitation.csv \
  --output-dir results
```

### 4. Software-only demonstration

For testing the analysis pipeline before real radiation/precipitation files are ready:

```bash
python LEC_reproduction.py \
  --lec-results paper_lec.csv \
  --demo-radiation \
  --simulate-precipitation \
  --output-dir demo_results
```

The synthetic precipitation is explicitly driven by gamma. Its correlation is **not empirical validation** and must not be presented as independent evidence for the paper's hypothesis.

## Radiation CSV

Either provide a time column and `Rn` in W m⁻²:

```text
time,Rn
2020-01-01,12.0
...
```

or provide `Q`, `alpha`, and `F`; the code uses `Rn = Q(1-alpha)-F`.

Radiation must correspond to the same spatial domain and time basis as the LEC calculation.

When `--resample D` is used, the workflow forms right-labelled complete daily
windows `(00:00, next 00:00]`, containing the four six-hour intervals ending
at 06, 12, 18 and 00 UTC. Incomplete bins are discarded; partial days are not
silently averaged.

## Precipitation CSV

Provide a time column and one of `Z`, `precipitation`, `precip`, `tp`, or `precip_mm_day`. Values are expected in mm/day for the paper plots.

## Outputs

- `analysis_timeseries.csv`
- `summary.csv`
- `01_time_series.png`
- `02_scatter.png`
- `03_conditional_pdf.png`
- `04_pdf_ratio_psi.png`
- `05_conditional_expectation.png`
- Toolkit stdout/stderr logs when Toolkit is run by the script

## ERA5 100-day pilot result

A 100-day regional ERA5 experiment was performed over:

- latitude: `17.5 S to 42.5 S`
- longitude: `60 W to 30 W`
- period: `2020-01-01` to `2020-04-09`

Using the corrected physical workflow:

- 6-hourly Pearson `r(gamma, Z) = 0.022692` (legacy result from the centered
  derivative; superseded pending recomputation with the interval-aligned tendency)
- aligned daily Pearson `r(gamma, Z) = -0.046642` (`n = 99`, complete 24-hour windows)
- aligned daily Spearman `rho(gamma, Z) = 0.200965`

The reported paper value:

`r = 0.865`

was not reproduced.

Robustness checks show that:

- previously reported 6-hourly threshold, rank-correlation and bootstrap results
  used the centered derivative and must be recomputed before being treated as
  final interval-aligned results
- the aligned daily Pearson relationship is near zero; threshold sensitivity is substantial (`r = 0.250702` at `|Rn| >= 5 W/m^2`, but near zero at higher thresholds)
- the aligned daily moving-block bootstrap 95% intervals include zero for both Pearson and Spearman across all tested block lengths
- the circular-shift test after threshold/lag search is not significant (`p = 0.606061`; maximum absolute observed correlation `= 0.386146` at threshold `|Rn| >= 40 W/m^2`, lag `4`, `n = 68`)
- large `|gamma|` values are strongly amplified when `Rn` approaches zero
- regional boundary-energy transports are dynamically important
- the strongest lagged relationship is not significant after circular-shift correction
- autocorrelation-aware block-bootstrap inference does not provide robust evidence for a strong relationship

This ERA5 experiment is a regional 100-day sensitivity analysis, not a global validation or rejection of the underlying physical hypothesis.


## Source used

LorenzCycleToolkit: https://github.com/daniloceano/LorenzCycleToolkit

The implementation intentionally calls the Toolkit instead of copying its LEC equations into this project, keeping the LEC diagnostic traceable to the maintained scientific package.

## Reproducibility audit

A detailed audit of the paper's numerical simulation and the reported `r = 0.865` result is available in:

[`REPRODUCIBILITY_AUDIT.md`](REPRODUCIBILITY_AUDIT.md)

The published correlation has not been reproduced from the available code and stated parameters. The audit documents the Appendix execution issue, deterministic reproduction, parameter sensitivity tests, Monte Carlo analysis, and atmospheric seed sweep.
