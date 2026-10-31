# ERA5 temporal-contract validation

## Status

**Verified for the current request configuration.** The surface request uses
the dataset **reanalysis-era5-single-levels** with **product_type = reanalysis**.
This is the hourly ERA5 reanalysis product, not ERA5-Land.

The three requested variables are:

| Variable | ERA5 short name | Units | Physical meaning |
|---|---|---|---|
| Total precipitation | **tp** | m | Accumulated water equivalent |
| Top net solar radiation | **tsr** | J m⁻² | Incoming minus reflected shortwave radiation at TOA |
| Top net thermal radiation | **ttr** | J m⁻² | Negative outgoing longwave radiation at TOA |

ECMWF documents hourly ERA5 reanalysis accumulations as totals over the
one-hour processing period ending at the validity timestamp. The same
interpretation is used for precipitation and radiative-flux accumulations.
Therefore, the values at 01:00, 02:00, ..., 06:00 UTC are six separate
one-hour interval totals for the six-hour interval (00:00, 06:00].

**Do not difference consecutive hourly values.** Summation is the correct
operation for the hourly ERA5 reanalysis product. This differs from ERA5-Land,
whose hourly accumulations are from 00 UTC to the forecast step and generally
require differencing.

Official references:

- [ECMWF/Copernicus accumulated-variable conversion table](https://confluence.ecmwf.int/pages/viewpage.action?pageId=212460134)
- [ECMWF parameter 178: top net solar radiation (tsr)](https://codes.ecmwf.int/grib/param-db/178)
- [ECMWF parameter 179: top net thermal radiation (ttr)](https://codes.ecmwf.int/grib/param-db/?id=179)
- [ERA5 data documentation and variable inventory](https://confluence.ecmwf.int/pages/viewpage.action?pageId=669811810)

The ECMWF vertical-flux convention is positive downwards. Thus tsr is
normally positive and ttr is normally negative. Their sum is net incoming
radiation at the top of the atmosphere, matching the paper's
Q(1-alpha)-F definition.

## Correct transformations

For a complete six-hour interval ending at time t:

    R_n(t) = [sum(tsr) + sum(ttr)] / (6 * 3600)  [W m-2]
    Z(t)   = sum(tp) * 1000 * 4                 [mm day-1]

The Z value is the six-hour mean precipitation rate expressed in mm/day.
Averaging four such six-hour rates over a complete day returns the 24-hour
mean precipitation rate, numerically equal to the 24-hour accumulation in mm.

Regional averaging is performed first, using cosine-latitude weights, then
the interval accumulations are summed. Since the weights are constant in
time and normalized by the weighted-mean operation, this is equivalent to
area-averaging each hourly field before temporal aggregation.

## Existing data coverage

The original files currently documented in the project contain:

| Dataset | Records | First timestamp | Last timestamp |
|---|---:|---|---|
| Pressure levels | 400 at 6-hour cadence | 2020-01-01 00 UTC | 2020-04-09 18 UTC |
| Surface | 2400 at hourly cadence | 2020-01-01 00 UTC | 2020-04-09 23 UTC |

With interval-ending timestamps and right-closed daily windows
(previous midnight, current midnight], the existing processed surface
series contains 399 complete six-hour intervals, which support 99 complete
daily windows. The first daily label is 2020-01-02 00 UTC and the last is
2020-04-09 00 UTC.

To obtain exactly 100 complete daily windows, one additional endpoint is
required in each raw dataset:

- Pressure-level state at 2020-04-10 00:00 UTC.
- Surface accumulated fields at 2020-04-10 00:00 UTC.

The surface records from 2020-04-09 19 UTC through 23 UTC are already present;
only the 2020-04-10 00 UTC endpoint is missing. No full re-download is needed.

## Safe endpoint extension

Run the following from the project root:

    python extend_era5_100d.py

The script requests only the two endpoint records from the same ERA5 datasets,
validates their coordinates and variables, and writes new files:

- era5_100d_extended.nc
- era5_surface_100d_extended.nc

The original NetCDF files are never modified. The expected extended
timelines are 401 pressure-level states and 2401 hourly surface records,
which provide 400 six-hour intervals and 100 complete daily windows.

Then process the extended surface data:

    python prepare_era5_surface.py --input-file era5_surface_100d_extended.nc --radiation-output radiation_100d_extended.csv --precipitation-output precipitation_100d_extended.csv

The processor reports the number of complete and discarded six-hour bins.
For the extended data, the expected result is 400 complete six-hour bins
ending from 2020-01-01 06 UTC through 2020-04-10 00 UTC.

## Interpretation limits

This verification settles the accumulation convention and the validity of
the existing hourly summation method. It does not by itself establish
that the regional experiment is a global atmospheric energy budget, nor
does it establish a physical or statistical relationship between gamma and
precipitation. Those require separate validation of the LEC domain,
boundary terms, sampling, and statistical model.
