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
