# Reproducibility Audit

## Scope

This document records reproducibility checks performed on the numerical simulation associated with the paper:

**Lorenz Energy Cycle, Radiation and Precipitation — Arefyan, Rajabi, Babaei (November 2025)**

The purpose of this audit is to distinguish:

1. the simulation printed in the paper,
2. the supplied/reconstructed `LEC.py`,
3. the corrected LorenzCycleToolkit-based workflow,
4. and results obtained from ERA5 data.

---

## 1. Reported paper result

The paper reports a Pearson correlation of:

`r = 0.865`

between the energy ratio `gamma(t)` and precipitation `Z(t)`.

The statistical-validation code printed in the paper calculates this quantity directly as:

`corr = np.corrcoef(gamma, Z)[0, 1]`

Therefore, the reported `0.865` is presented as the raw contemporaneous Pearson correlation between `gamma` and `Z`, not as a correlation of conditional means or a lagged correlation.

---

## 2. Printed Appendix code does not execute as written

The Appendix defines the synthetic zonal wind `u` with shape:

`(100, 36, 1, 1)`

while `v` and `T` have shape:

`(100, 36, 72, 7)`

The subsequent `xarray.Dataset` assigns all variables the dimensions:

`(time, lat, lon, lev)`

with:

`lon = 72`
`lev = 7`

Executing the Appendix formulation therefore produces:

`ValueError: conflicting sizes for dimension 'lon'`

This means the Appendix simulation is not directly executable in its printed form without modifying or broadcasting `u`.

Test:

`paper_appendix_shape_check.py`

---

## 3. Repository LEC.py differs from the printed Appendix

The executable `LEC.py` contains changes relative to the printed paper code, including full-size stochastic fields for the atmospheric variables.

It also uses a simplified placeholder LEC calculation rather than a complete Lorenz Energy Cycle diagnostic.

The energy reservoirs are calculated using simplified zonal means, variances, and squared temperature fields.

Therefore, results from this script should be treated as a synthetic demonstration rather than a physical LEC calculation.

---

## 4. Direct execution of supplied LEC.py

A direct run produced:

`Correlation between gamma and Z: 0.029`

Five independent process executions produced approximately:

`-0.002`
`-0.041`
`-0.012`
`-0.022`
` 0.029`

The reported value `0.865` was not reproduced.

---

## 5. Deterministic seeded reproduction

A deterministic copy was created as:

`LEC_seeded.py`

with:

`np.random.seed(42)`

placed before synthetic atmospheric data generation.

Result:

`Correlation between gamma and Z: 0.009`

More precisely:

`r = 0.0087586048`

The resulting gamma statistics were:

`min   = -0.03032724`
`max   =  0.01720286`
`mean  = -0.00058403`
`std   =  0.00633585`

The precipitation equilibrium mean was defined as:

`mu_Z = 3.0 + 5.0 * gamma`

giving:

`mu_Z std = 0.03167923 mm/day`

while the stochastic precipitation noise parameter is:

`sigma_Z = 1.5`

Thus the stochastic forcing is much larger than the gamma-dependent variation in the precipitation equilibrium mean.

---

## 6. Coupling-strength sensitivity

Keeping the original precipitation dynamics but increasing the gamma coupling from `5` up to `500000` did not reproduce the reported contemporaneous correlation.

At very large coupling, the lag-one correlation approached approximately:

`r_lag1 ~ 0.486`

while the contemporaneous correlation remained small or negative.

Therefore simply increasing the coefficient multiplying gamma does not reproduce `r = 0.865` under the original mean-reversion dynamics.

Test:

`coupling_sweep.py`

---

## 7. Noise sensitivity

Using:

`theta = 0.1`
`coupling = 5`

and reducing precipitation noise from:

`sigma = 1.5`

to:

`sigma = 0`

still produced only approximately:

`r0     = 0.382`
`r_lag1 = 0.401`

Therefore stochastic noise alone does not explain the discrepancy.

---

## 8. Mean-reversion sensitivity

With noise removed:

`sigma = 0`

and coupling retained at:

`coupling = 5`

increasing `theta` produced increasingly strong lag-one correlations.

Examples:

`theta = 0.72 -> r_lag1 = 0.856775`
`theta = 0.74 -> r_lag1 = 0.868654`
`theta = 0.80 -> r_lag1 = 0.906201`
`theta = 1.00 -> r_lag1 = 1.000000`

A value close to `0.865` can therefore be produced under substantially different parameters, but the paper uses `theta = 0.1`, uses `sigma = 1.5`, and reports contemporaneous correlation rather than lag-one correlation.

This is therefore not a reproduction of the reported result.

---

## 9. Gamma autocorrelation

The lag-one autocorrelation of the deterministic gamma series was:

`corr(gamma[t], gamma[t-1]) = 0.216697`

This is not sufficiently strong to explain the reported precipitation correlation through persistence alone.

---

## 10. Monte Carlo test of the author's precipitation model

Using the same deterministic gamma series and the published precipitation parameters:

`theta    = 0.1`
`coupling = 5`
`sigma    = 1.5`

10,000 independent precipitation realizations were generated.

Results:

`runs                 = 10000`
`mean_r               = 0.060030`
`std_r                = 0.055900`
`min_r                = -0.188255`
`max_r                = 0.290918`
`95th percentile      = 0.149420`
`99th percentile      = 0.187804`
`count(r >= 0.865)    = 0`
`fraction(r >= 0.865) = 0.0`

No realization approached the reported correlation.

Test:

`monte_carlo_author_model.py`

---

## 11. Full atmospheric seed sweep

The complete synthetic atmospheric generation plus precipitation model was repeated for 100 atmospheric random seeds.

Results:

`runs              = 100`
`mean_r            = -0.002348`
`std_r             = 0.059979`
`min_r             = -0.158356`
`max_r             = 0.138179`
`best_seed         = 82`
`95th percentile   = 0.083050`
`99th percentile   = 0.121745`
`count(r >= 0.865) = 0`

Changing the atmospheric random seed did not reproduce the reported result.

Test:

`full_seed_sweep.py`

---

## 12. Conditional-mean hypothesis

The possibility that `0.865` represented a correlation based on the binned conditional expectation `E[Z|gamma]` was also tested.

Results:

`raw_r              = 0.008759`
`conditional_mean_r = 0.210288`
`number_of_bins     = 9`

Therefore the reported `0.865` is not reproduced by this interpretation either.

---

## 13. Current reproducibility conclusion

Using the available paper text, printed Appendix code, supplied/reconstructed executable code, deterministic seeding, parameter sweeps, Monte Carlo simulations, and atmospheric-seed sweeps:

**The reported correlation `r = 0.865` has not been reproduced.**

The available implementation instead produces correlations close to zero under the stated model parameters.

The tests performed so far do not identify a combination of the published code and published parameters that generates the reported value.

Possible explanations that remain open include:

- a different unpublished simulation version,
- different parameters,
- different synthetic data,
- a different random-number sequence,
- or a result generated using methodology not represented in the supplied code.

No conclusion about the origin of the discrepancy should be made without additional provenance from the original simulation.

---

## 14. Corrected physical workflow

The reproduction project separately replaces the simplified placeholder LEC calculation with:

`LorenzCycleToolkit 2.0.0`

Toolkit commit:

`d38cda7e37d8e8a3a937a5919640a94bef19e34a`

The corrected workflow calculates:

`E_L = Az + Ae + Kz + Ke`

and:

`gamma(t) = (dE_L/dt) / Rn(t)`

using physically diagnosed LEC reservoirs and ERA5 atmospheric data.

Results from that workflow must be treated separately from the synthetic simulation reported in the original paper.

---

## Reproducibility environment

`Python             3.13.3`
`numpy              2.5.3`
`pandas             3.0.6`
`scipy              1.18.1`
`matplotlib         3.11.1`
`xarray             2024.2.0`
`dask               2024.7.0`
`netCDF4            1.7.4`
`LorenzCycleToolkit 2.0.0`

Toolkit commit:

`d38cda7e37d8e8a3a937a5919640a94bef19e34a`

---

## 15. Reconstruction of the printed Appendix

The printed Appendix required two mechanical corrections before it could execute:

1. The synthetic zonal wind `u` had shape:

`(100, 36, 1, 1)`

while the Dataset expected:

`(100, 36, 72, 7)`

It was therefore broadcast to the declared longitude and pressure-level dimensions.

2. The printed eddy expressions used:

`u_zm[..., np.newaxis]`

which gives shape:

`(100, 36, 7, 1)`

and is incompatible with:

`(100, 36, 72, 7)`

The mechanically consistent form is:

`u_zm[:, :, np.newaxis, :]`

with the same correction applied to `v_zm` and `T_zm`.

No model parameters were changed.

After these two execution corrections, the reconstructed Appendix produced approximately:

`Correlation between gamma and Z = 0.0324`

with:

`gamma std = 0.00554`

This does not reproduce the reported:

`r = 0.865`

and the gamma variability is also substantially larger than the order of `10^-4` described in the paper.

Test:

`paper_appendix_reconstructed.py`

### Appendix atmospheric-seed sweep

The corrected Appendix reconstruction was then evaluated across 100 random seeds for the synthetic temperature field.

Results:

`runs              = 100`
`mean_r            = 0.007063`
`std_r             = 0.059884`
`min_r             = -0.122729`
`max_r             = 0.168062`
`best_seed         = 39`
`best_r             = 0.168062`
`95th percentile   = 0.097309`
`99th percentile   = 0.145740`
`count(r >= 0.865) = 0`

Gamma standard deviation across the sweep was:

`mean = 0.005144`
`min  = 0.003752`
`max  = 0.008217`

Therefore, the published correlation and the stated gamma scale were not reproduced by the printed Appendix after the minimum corrections required for execution.

Test:

`paper_appendix_seed_sweep.py`

---

## 16. Legacy NumPy RNG verification

The published precipitation simulation uses the legacy NumPy random-number interface:

`np.random.seed(...)`

and:

`np.random.randn()`

To verify whether the random-number generator implementation could explain the discrepancy in the reported correlation, the precipitation model was repeated using NumPy's legacy `RandomState` generator.

The deterministic gamma series was held fixed, and the published precipitation parameters were retained:

`theta = 0.1`

`coupling = 5.0`

`sigma = 1.5`

`base_mean = 3.0`

A total of 10,000 independent precipitation realizations were generated using seeds 0 through 9999.

Results:

`runs                 = 10000`
`mean_r               = 0.059442`
`std_r                = 0.056381`
`min_r                = -0.173672`
`max_r                = 0.265705`
`best_seed            = 3569`
`best_r               = 0.265705`
`95th percentile      = 0.149207`
`99th percentile      = 0.188780`
`count(r >= 0.865)    = 0`
`fraction(r >= 0.865) = 0.0`

Therefore, using the same legacy NumPy random-number family as the published Appendix does not reproduce the reported correlation.

The RNG implementation does not account for the discrepancy between the available simulation and the reported:

`r = 0.865`

Test:

`legacy_rng_precipitation_sweep.py`

---

## 17. Joint atmospheric and precipitation seed sweep

To test whether the reported correlation could arise from a specific combination of atmospheric and precipitation random seeds, both stochastic components were varied simultaneously.

The corrected Appendix reconstruction was evaluated for:

`100 atmospheric seeds`

and:

`100 precipitation seeds`

giving:

`10000 total seed combinations`

The published precipitation parameters were retained:

`theta = 0.1`

`coupling = 5.0`

`sigma = 1.5`

`base_mean = 3.0`

Results:

`runs                         = 10000`
`mean_r                       = -0.002015`
`std_r                        = 0.064004`
`min_r                        = -0.230243`
`max_r                        = 0.260286`
`best_atmospheric_seed        = 61`
`best_precipitation_seed      = 73`
`best_r                       = 0.260286`
`95th percentile              = 0.103910`
`99th percentile              = 0.149802`
`99.9th percentile            = 0.206092`
`count(r >= 0.865)            = 0`
`fraction(r >= 0.865)         = 0.0`

Therefore, varying both available random sources simultaneously does not reproduce the reported:

`r = 0.865`

No tested atmospheric/precipitation seed combination approached the published correlation.

Test:

`paper_appendix_joint_seed_sweep.py`

---

## 18. ERA5 100-day real-data analysis

The physically corrected workflow was also evaluated using ERA5 atmospheric, radiation, and precipitation data.

### 6-hourly analysis

Results:

`n_samples          = 399`
`Pearson r(gamma,Z) = 0.022692`
`gamma mean         = -0.011245`
`gamma std          = 0.421651`
`Rn mean            = 63.714218 W/m2`
`dEL/dt mean        = 0.245221 W/m2`
`Z mean             = 4.144665 mm/day`

The contemporaneous correlation is therefore close to zero.

### Daily analysis - legacy grouping (superseded)

The values below use the earlier daily grouping and are retained for historical traceability. They are superseded by the complete-window-aligned daily analysis in the updated temporal-alignment and bootstrap diagnostics.

Legacy results:

`n_samples          = 100`
`Pearson r(gamma,Z) = 0.109124`
`gamma mean         = 0.016706`
`gamma std          = 0.488383`
`Rn mean            = 63.930227 W/m2`
`dEL/dt mean        = 0.253393 W/m2`
`Z mean             = 4.144777 mm/day`

The legacy daily contemporaneous correlation was positive but weak. It must not be interpreted as the corrected aligned-daily result.

### Sensitivity to small net-radiation values

Because:

`gamma = (dEL/dt) / Rn`

small values of `|Rn|` can strongly amplify gamma.

The correlation was therefore recalculated after progressively excluding small `|Rn|` values.

For the 6-hourly data, the correlation remained small across all tested thresholds.

For the daily data, the following threshold results belong to the legacy grouping and are superseded by the corrected complete-window-aligned threshold analysis:

`|Rn| >= 5   -> r = 0.233653`
`|Rn| >= 10  -> r = 0.108506`
`|Rn| >= 20  -> r = 0.024552`
`|Rn| >= 40  -> r = 0.008150`
`|Rn| >= 50  -> r = 0.018089`

This indicates that the apparent daily relationship is not robust to the treatment of small net-radiation denominators.

Test:

`rn_threshold_sensitivity.py`

### Lag and multiple-testing robustness

A search across:

* radiation thresholds from `0.5` to `50 W/m2`
* lags from `-10` to `+10` days

The current corrected analysis found the strongest observed relationship at:

`threshold = 40 W/m2`
`lag       = +4 days`
`n         = 68`
`r         = -0.386146`

The circular-shift null test repeats the complete threshold-and-lag search for each valid nonzero circular shift. The current results are:

`valid circular shifts = 98`
`corrected p-value = 0.606061`
`95th percentile of null maximum |r| = 0.446396`

The observed maximum absolute correlation:

`|r| = 0.386146`

is below the 95th percentile of the null distribution.

Therefore, the strongest lagged relationship found in this exploratory 100-day analysis is not statistically significant after accounting for the threshold and lag search.

These results supersede the earlier reported values (`r = -0.380657`, `n = 69`, corrected `p = 0.540000`, and null 95th percentile `= 0.407977`).

Test:

`circular_shift_test.py`

### Current real-data conclusion

For this 100-day ERA5 analysis, the corrected physical LEC workflow does not reproduce the paper's reported:

`r = 0.865`

The contemporaneous correlations are weak, sensitivity to the radiation denominator is substantial, and the strongest lagged correlation is not significant under the circular-shift robustness test.

These results apply only to the present ERA5 analysis configuration and should not be interpreted as a general rejection of an energy-precipitation relationship.

---

## 19. ERA5 diagnostic robustness checks

Additional diagnostics were performed to test whether the weak ERA5 relationship could be explained by numerical processing choices, outliers, or regional energy-budget structure.

### Daily derivative consistency

Two daily constructions were compared:

1. average the 6-hourly `dE_L/dt`, then form daily gamma
2. first average `E_L` daily, then recompute `dE_L/dt`

Legacy results from the earlier daily grouping (superseded; not recomputed with the corrected complete-window alignment):

`current daily r      = 0.109124`
`recomputed daily r   = 0.111612`
`corr(two gamma)      = 0.982790`

Therefore, the weak daily correlation is not explained by the order of daily resampling and differentiation.

Test:

`daily_derivative_consistency.py`

### Gamma distribution and denominator amplification

The observed gamma distribution is strongly heavy-tailed.

For the 6-hourly analysis:

`gamma min            = -3.401993`
`gamma max            = 5.266565`
`gamma median         = 0.002946`
`gamma 99th percentile= 0.695345`

For the daily analysis:

`gamma min            = -1.900859`
`gamma max            = 3.861180`
`gamma median         = -0.008780`
`gamma 99th percentile= 1.216261`

Large `|gamma|` values are strongly associated with small `|Rn|`.

Observed correlations:

`corr(|gamma|, 1/|Rn|) = 0.823582` for 6-hourly data

and:

`corr(|gamma|, 1/|Rn|) = 0.641886` for daily data

This confirms that the ratio is numerically amplified when the radiation denominator approaches zero.

Tests:

`gamma_distribution_check.py`

`gamma_outlier_diagnosis.py`

### Rank-based correlation robustness

Spearman correlation was also evaluated to reduce sensitivity to extreme values.

For the 6-hourly data, Spearman correlation remained close to zero across all tested radiation thresholds.

For the daily data, the following are legacy values from the earlier daily grouping. They are retained for historical traceability and are not the corrected aligned-daily threshold results:

`|Rn| >= 0.5 -> Spearman = 0.230747`

`|Rn| >= 5   -> Spearman = 0.191576`

`|Rn| >= 10  -> Spearman = 0.082586`

`|Rn| >= 20  -> Spearman = 0.061374`

`|Rn| >= 40  -> Spearman = 0.012276`

`|Rn| >= 50  -> Spearman = 0.019869`

Thus, the weak daily relationship also disappears as small-denominator samples are removed.

Test:

`robust_correlation_check.py`

### ERA5 input and processing consistency

The ERA5 pressure-level dataset contains:

`400` six-hourly time steps

with pressure levels:

`1000, 850, 700, 500, 300, 200, 100 hPa`

over the regional domain:

`17.5 S to 42.5 S`

`60 W to 30 W`

The atmospheric variables and units are consistent with the LorenzCycleToolkit input requirements:

- geopotential
- temperature
- zonal wind
- meridional wind
- pressure vertical velocity

The surface ERA5 dataset contains:

`2400` hourly records

for:

- top net short-wave radiation
- top net long-wave radiation
- total precipitation

The generated 6-hourly radiation and precipitation CSV files reproduce the transformations from the raw NetCDF data to numerical precision.

Maximum absolute differences were:

`radiation    = 1.18e-11`

`precipitation= 2.18e-13`

Tests:

`era5_pressure_metadata_check.py`

`era5_surface_metadata_check.py`

`era5_surface_processing_consistency.py`

### LorenzCycleToolkit output consistency

The raw LorenzCycleToolkit result contains `400` time steps.

The final analysis contains `399` time steps because the first atmospheric state at:

`2020-01-01 00:00`

has no complete preceding 6-hour surface interval.

For all common timestamps, `Az`, `Ae`, `Kz`, and `Ke` agree with the raw toolkit result to floating-point precision.

The independently calculated:

`dE_L/dt = d(Az + Ae + Kz + Ke)/dt`

also agrees with the sum of the toolkit finite-difference energy tendencies.

Results:

`max absolute difference = 1.82e-14`

`correlation             = 1.0`

Tests:

`lec_output_consistency.py`

`lec_derivative_consistency.py`

### Regional boundary-energy terms

Because this ERA5 experiment uses a finite regional domain, LorenzCycleToolkit includes boundary-energy transport terms.

For the 400-step regional budget:

`mean |dE_L/dt| = 4.753386 W/m2`

`mean |B_total| = 7.235848 W/m2`

and therefore:

`mean |B_total| / mean |dE_L/dt| = 1.522251`

The total budget closes to numerical precision:

`maximum closure error = 7.11e-15 W/m2`

The correlation between the total energy tendency and the total boundary term is:

`r = 0.576293`

Thus, boundary transport is dynamically important in this regional experiment and cannot be treated as negligible.

Test:

`regional_energy_budget_check.py`

### Boundary-adjusted sensitivity - legacy daily results pending realignment

The daily values in this subsection were calculated with the earlier daily grouping. They have not yet been recomputed using the corrected complete-window alignment; treat them as legacy sensitivity results, not as updated aligned-daily estimates.

As a diagnostic only, the diagnosed boundary contribution was removed from the total regional energy tendency before forming the radiation ratio.

At 6-hour resolution, the resulting correlations remained weak:

`Pearson ≈ -0.07 to -0.20`

and:

`Spearman ≈ -0.14 to -0.18`

across the tested radiation thresholds.

At daily resolution, the boundary-adjusted correlations also remained modest and threshold-dependent.

The largest tested daily Pearson value in this legacy analysis was:

`r = 0.257811`

at:

`|Rn| >= 50 W/m2`

with only:

`n = 62`

samples.

These calculations are sensitivity diagnostics only. They do not redefine the paper's gamma and do not establish a direct equivalence between the regional residual budget and the paper's global-like energy relation.

Test:

`regional_boundary_sensitivity.py`

### Updated ERA5 assessment

The weak ERA5 result is not attributable to:

- a mismatch between raw ERA5 and processed radiation/precipitation
- a mismatch between LorenzCycleToolkit output and the analysis file
- an error in the total energy derivative
- the order of daily resampling and differentiation
- Pearson sensitivity alone

The regional experiment is additionally affected by dynamically important boundary-energy transports and by numerical amplification of gamma when `Rn` approaches zero.

Therefore, this 100-day regional ERA5 experiment should be interpreted as an exploratory sensitivity test rather than a direct global validation of the paper's reported correlation.

---

## 20. Autocorrelation-aware uncertainty analysis

> **Temporal-alignment update (2026-10-30):** The 6-hourly bootstrap figures
> below were produced from the earlier `analysis_timeseries.csv`, whose
> `gamma` used a centered `np.gradient(E_L)`. ERA5 accumulated surface fields
> at timestamp `t` represent the interval ending at `t`; the production
> workflow now uses `[E_L(t)-E_L(t-6h)]/6h` for that timestamp. Consequently,
> the old 6-hourly bootstrap estimates and any 6-hourly correlations based on
> the centered derivative are historical diagnostics, not final interval-aligned
> estimates. Re-run the updated analysis and bootstrap scripts before citing
> 6-hourly values. The aligned-daily calculations in this section already
> reconstruct the interval tendency explicitly.

Because precipitation and gamma are time series, ordinary independent-sample confidence intervals can underestimate uncertainty when serial dependence is present.

### Autocorrelation diagnostics

The 6-hourly precipitation series exhibits substantial short-lag persistence:

`lag 1 = 0.888205`

`lag 2 = 0.726658`

`lag 4 = 0.505357`

The 6-hourly gamma series has little lag-1 persistence but shows a notable daily-scale component:

`lag 4 = 0.351430`

The previously reported daily lag-1 values (`gamma = -0.085837`, `Z = 0.567842`) were computed from the old saved daily grouping and should be treated as legacy diagnostics until recomputed from the aligned 99-day series.

These diagnostics motivate the use of moving-block bootstrap rather than an iid bootstrap.

Test:

`autocorrelation_diagnostics.py`

### Moving-block bootstrap

A moving-block bootstrap was applied to preserve short-range temporal dependence.

For the 6-hourly data, using a block length of 8 samples and 10,000 bootstrap realizations:

`Pearson r = 0.022692`

`95% CI = [-0.065701, 0.102600]`

and:

`Spearman r = -0.017398`

`95% CI = [-0.124891, 0.080355]`

Both intervals include zero.

The original saved daily analysis used a superseded daily grouping and is not used for the updated daily inference.

Daily data were reconstructed from complete right-labelled 24-hour windows, each containing four 6-hour samples in `(day 00 UTC, next day 00 UTC]`. This yields 99 complete days, labelled from `2020-01-02 00:00` through `2020-04-09 00:00`.

Using a block length of 2 samples and 10,000 bootstrap realizations:

`Pearson r = -0.046642`

`95% CI = [-0.182829, 0.422878]`

and:

`Spearman r = 0.200965`

`95% CI = [-0.023718, 0.410465]`

Both intervals include zero.

Test:

`block_bootstrap_correlation.py`

### Block-length sensitivity

Because bootstrap inference can depend on block length, the analysis was repeated over multiple block sizes.

For the 6-hourly analysis, all tested block lengths:

`4, 8, 12, 16`

produced Pearson and Spearman 95% intervals that included zero.


For the correctly aligned 99-day series, Pearson intervals included zero for every tested block length (`2, 3, 4, 5, 7, 10`). Spearman intervals also included zero at every tested block length.

Examples:

`block = 2 -> Pearson 95% CI = [-0.181337, 0.416217]; Spearman 95% CI = [-0.021064, 0.412933]`

`block = 5 -> Pearson 95% CI = [-0.166104, 0.432891]; Spearman 95% CI = [-0.016236, 0.439314]`

`block = 10 -> Pearson 95% CI = [-0.127848, 0.353778]; Spearman 95% CI = [-0.019845, 0.420222]`

Across all tested block lengths, the 95% bootstrap confidence intervals for both Pearson and Spearman correlations include zero in the correctly aligned 99-day series. These results do not provide robust evidence of a non-zero contemporaneous correlation in this regional pilot.

Test:

`block_bootstrap_sensitivity.py`

### Updated statistical interpretation

The autocorrelation-aware analysis reinforces the earlier robustness results.

At 6-hour resolution, there is no stable evidence for a contemporaneous gamma-precipitation relationship.

At daily resolution, a weak positive rank association can appear under some short-block bootstrap choices, but it is sensitive to both:

- radiation-denominator thresholding
- bootstrap block length

Therefore, the current 100-day regional ERA5 experiment does not provide robust statistical support for a strong gamma-precipitation relationship comparable to the paper's reported:

`r = 0.865`


---

## 21. ERA5 hourly accumulation contract — verified 2026-10-31

### Dataset identity and official convention

The current surface download script requests the Copernicus dataset
**reanalysis-era5-single-levels** with **product_type = reanalysis**.
It does not request ERA5-Land.

The requested surface variables are:

- **tp**: total precipitation, metres of water equivalent
- **tsr**: top net solar radiation, J m⁻²
- **ttr**: top net thermal radiation, J m⁻²

ECMWF's documentation defines the hourly ERA5 reanalysis accumulation at
validity time t as the total accumulated over the preceding one-hour
processing interval ending at t. Thus records at 01, 02, ..., 06 UTC are
six distinct one-hour accumulations for (00, 06].

**Conclusion: sum the six hourly records. Do not difference consecutive
hourly records.** Differencing is associated with other accumulation
conventions, notably ERA5-Land hourly forecast-step accumulations; it is
not the correct operation for this ERA5 hourly reanalysis request.

Official references:

- https://confluence.ecmwf.int/pages/viewpage.action?pageId=212460134
- https://codes.ecmwf.int/grib/param-db/178
- https://codes.ecmwf.int/grib/param-db/?id=179
- https://confluence.ecmwf.int/pages/viewpage.action?pageId=669811810

ECMWF uses the downward-positive convention for vertical radiative fluxes.
tsr is incoming shortwave minus reflected shortwave radiation at TOA.
ttr is the negative of outgoing longwave radiation (OLR). Therefore
tsr + ttr is net incoming radiation at TOA and is consistent with the
paper's Q(1-alpha)-F expression.

The absence of GRIB_startStep, GRIB_endStep and GRIB_stepRange from the
current NetCDF files is not sufficient reason to redownload the full data:
the dataset identity, request configuration, variable definitions and
ECMWF documentation jointly establish the accumulation convention.

### Valid transformations

For each complete six-hour interval ending at t:

    R_n(t) = [sum(tsr) + sum(ttr)] / 21600  W m-2
    Z(t)   = sum(tp) * 1000 * 4             mm day-1

The existing method of area-averaging hourly fields with cosine-latitude
weights and then summing the interval accumulations is consistent with the
linear area and time aggregation.

### Actual coverage and required endpoint

The local audit recorded:

- Pressure levels: 400 states, 2020-01-01 00 through 2020-04-09 18 UTC.
- Surface: 2400 hourly records, 2020-01-01 00 through 2020-04-09 23 UTC.
- Processed surface series: 399 complete six-hour intervals, 2020-01-01 06 through 2020-04-09 18 UTC.

Under the required interval-ending convention, complete daily windows are
right-closed (previous midnight, current midnight] windows containing
four six-hour intervals. The current data therefore support **99 complete
daily windows**, labelled 2020-01-02 00 through 2020-04-09 00 UTC. The
previously saved 100-row daily CSV must not be described as 100 complete
days without a complete-window count.

To obtain 100 complete daily windows, only the final endpoint is missing:

- One pressure-level state at 2020-04-10 00 UTC.
- One hourly surface accumulation at 2020-04-10 00 UTC.

The surface records from 2020-04-09 19 through 23 UTC already exist. No
full-period download is required.

### Code changes and validation status

The repository now includes:

- ERA5_TEMPORAL_VALIDATION.md: full convention, unit and coverage record.
- era5_surface_processing.py: tested aggregation of hourly accumulations.
- era5_metadata.py: validates ERA5 pressure/surface units and GRIB step types when present.
- prepare_era5_surface.py: area-weighted processing with explicit inputs
  and outputs.
- extend_era5_100d.py: requests only the two missing endpoint records and
  writes new extended NetCDF files without modifying the originals.
- analysis_config.py: selects the extended data set automatically once
  all extended inputs exist.
- Strict timestamp matching and non-finite-value validation in the shared
  and main analysis loaders.
- Time-axis preservation for small-denominator gamma masks.
- Rejection of discontinuous daily windows before time-series inference.

The automated tests cover interval-ending tendencies, exact timestamp
alignment, complete daily windows, missing-data gaps, hourly accumulation
summation, unit conversions, and positive-support KDE normalization.

**Verified:** ERA5 accumulation convention and mathematical transformations.

**Verified in CI:** software tests and syntax compilation for the pipeline
entry points (see the latest GitHub Actions run on this branch).

**Pending local validation:** execute the endpoint extension and rerun the
actual NetCDF-to-LEC pipeline. Until that run is complete, the old pilot
correlations and bootstrap estimates remain historical results and must
not be presented as the final interval-aligned 100-day analysis.



---

## 22. Conditional precipitation probability outputs

The paper defines the conditional density P(Z,t | gamma,t) and, in Eq. 40,
defines the PDF ratio:

    Psi(Z, gamma; t) = P(Z, t | gamma, t) / P(gamma, t)

These two objects must not be conflated. The conditional density is a
probability density over precipitation amounts; integrating it over an
interval [z1, z2] gives the probability that precipitation lies in that
interval, conditional on gamma. The Eq. 40 quantity Psi is a ratio of
densities. Although the paper describes it as representing a probability,
it is not itself a normalized event probability.

The analysis now saves both the paper's PDF ratio and proper conditional
event-probability outputs:

- conditional_pdf.csv: p(Z | gamma)
- conditional_cdf.csv: P(Z <= z | gamma)
- precipitation_exceedance_probability.csv: P(Z > z_threshold | gamma)
  for every precipitation threshold on the saved Z grid
- psi.csv: the Eq. 40 density ratio

No wet-day or heavy-precipitation threshold is hard-coded because the paper
does not specify one. A researcher can select a physically meaningful
threshold and read the corresponding exceedance probability from the
saved matrix. This also avoids reporting the PDF ratio as though it were
the probability of a precipitation event.

The CDF and exceedance outputs are numerically integrated from the
non-negative-support conditional KDE and normalized over the displayed
precipitation grid. They are in-sample descriptive probabilities; they do
not constitute out-of-sample forecast skill. Any claim of predictive skill
requires blocked out-of-sample validation and probability calibration.



A further limitation is the treatment of zero precipitation. The current
Gaussian KDE models Z as a continuous non-negative variable; it does not
represent a discrete probability mass at exactly zero. Consequently,
P(Z > z_threshold | gamma) is meaningful for positive thresholds on the
saved grid, but the limit at zero should not be interpreted as a calibrated
rain/no-rain occurrence probability. A wet-day occurrence model requires
the research team to define a wet-day threshold and then fit/evaluate a
binary or hurdle model. The paper does not specify such a threshold, so
none is hard-coded here.

