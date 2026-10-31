# Scientific method and implementation decisions

## Scope

This repository evaluates the relationship between the Lorenz Energy Cycle (LEC), top-of-atmosphere net radiation, and precipitation for one regional ERA5 experiment. The synthetic reproduction and ERA5 analysis are separate experiments; their statistics must never be combined.

Current ERA5 configuration:
- Longitude: 60°W to 30°W; latitude: 42.5°S to 17.5°S.
- Pressure levels: 1000, 850, 700, 500, 300, 200 and 100 hPa.
- Analysis interval: (2020-01-01 00:00 UTC, 2020-04-10 00:00 UTC].
- Sampling: six hours; 400 complete six-hour intervals and 100 complete daily windows.

## LEC reservoirs and tendency

LorenzCycleToolkit diagnoses zonal available potential energy Az, eddy available potential energy Ae, zonal kinetic energy Kz, and eddy kinetic energy Ke. The total energy is E_L = Az + Ae + Kz + Ke. The reservoirs are in J m-2.

The primary interval-ending tendency is the backward finite difference:

    dE_L/dt(t) = [E_L(t) - E_L(t-6h)] / 21600  [W m-2]

The first state has no preceding six-hour interval and has no tendency. A centered derivative is diagnostic only and is not used in gamma.

## ERA5 temporal convention and transformations

The surface request uses hourly ERA5 reanalysis, not ERA5-Land. The hourly tp, tsr and ttr values are one-hour accumulations ending at their validity timestamps. Six hourly values are summed, not differenced.

    R_n(t) = [sum(tsr) + sum(ttr)] / 21600  [W m-2]
    Z(t)   = sum(tp) * 1000 * 4             [mm day-1]

The Z transformation expresses a six-hour accumulation as a daily rate. Averaging four six-hour rates over a complete day equals the 24-hour accumulation in mm. Regional means use cosine-latitude weights and the same spatial domain for LEC, radiation and precipitation.

Daily bins are right-closed windows (t-24h, t], labelled by their ending midnight. A bin is complete only when all four six-hour samples are present and finite for required variables. The 100 labels are 2020-01-02 00:00 through 2020-04-10 00:00 UTC.

## Energy ratio and dissipation limitation

    gamma(t) = [dE_L/dt] / R_n(t)

Both terms are W m-2, so gamma is dimensionless. By default gamma is masked when abs(R_n) < 0.5 W m-2. The timestamp remains in the series with gamma=NaN; it is not deleted. The threshold is configurable and sensitivity scripts evaluate alternatives.

Standard ERA5 input does not provide the friction-force components required for the Toolkit's direct Dz and De pathway. Residual terms RKz and RKe include more than physical frictional dissipation and are not relabelled as Dz or De. The primary gamma therefore uses the directly diagnosed total reservoir tendency rather than claiming a Gz+Ge-Dz-De decomposition.

## Probability outputs

The workflow estimates a joint KDE and derives:
- p(Z|gamma): conditional precipitation density over non-negative Z.
- Psi: the PDF ratio in the paper; it is a density ratio, not itself an event probability.
- P(Z<=z|gamma): conditional CDF.
- P(Z>z|gamma): conditional exceedance probability at every threshold on the saved Z grid.

No arbitrary wet-day threshold is introduced. A user-facing event probability requires a scientifically justified threshold. Gamma values outside the 1st and 99th percentiles are trimmed for KDE as described in the Appendix; precipitation values are not trimmed. Numerical integration is over non-negative precipitation support.

## Statistical inference and limitations

Time-series diagnostics preserve chronology. Irregular sampling and incomplete interior days are rejected rather than compressed. The repository includes block-bootstrap, threshold-sensitivity, autocorrelation, circular-shift and regional-boundary diagnostics. Circular-shift inference repeats the complete threshold/lag search for each shift.

This is a regional 100-day experiment over a finite atmospheric domain with non-negligible boundary-energy transports. It is not a global atmospheric energy budget and cannot establish a global causal relationship or reject the underlying physical hypothesis. The paper's synthetic Pearson correlation r=0.865 has not been reproduced from the available Appendix implementation and stated parameters. See REPRODUCIBILITY_AUDIT.md; historical pilot values are not substitutes for the final extended run.