"""Unit tests for interval-ending LEC/radiation temporal alignment."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from LEC_reproduction import _resample_if_requested, load_lec_results
from era5_analysis import load_interval_analysis


class TemporalAlignmentTests(unittest.TestCase):
    def _write_lec_csv(self, frame):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "lec.csv"
        frame.to_csv(path, index=False)
        return path

    def test_energy_tendency_is_interval_ending(self):
        times = pd.date_range("2020-01-01 00:00", periods=4, freq="6h")
        frame = pd.DataFrame(
            {
                "time": times,
                "Az": [0.0, 21600.0, 43200.0, 64800.0],
                "Ae": [0.0, 0.0, 0.0, 0.0],
                "Kz": [0.0, 0.0, 0.0, 0.0],
                "Ke": [0.0, 0.0, 0.0, 0.0],
            }
        )
        result = load_lec_results(self._write_lec_csv(frame))

        self.assertTrue(np.isnan(result["dE_L_dt"].iloc[0]))
        np.testing.assert_allclose(result["dE_L_dt"].iloc[1:].to_numpy(), np.ones(3))
        np.testing.assert_allclose(result["dE_L_dt_centered"].to_numpy(), np.ones(4))

    def test_missing_reservoir_invalidates_total_energy(self):
        times = pd.date_range("2020-01-01 00:00", periods=4, freq="6h")
        frame = pd.DataFrame(
            {
                "time": times,
                "Az": [0.0, 21600.0, 43200.0, 64800.0],
                "Ae": [0.0, np.nan, 0.0, 0.0],
                "Kz": [0.0, 0.0, 0.0, 0.0],
                "Ke": [0.0, 0.0, 0.0, 0.0],
            }
        )
        result = load_lec_results(self._write_lec_csv(frame))

        self.assertTrue(np.isnan(result["E_L"].iloc[1]))
        self.assertTrue(np.isnan(result["dE_L_dt"].iloc[1]))
        self.assertTrue(np.isnan(result["dE_L_dt"].iloc[2]))
        self.assertAlmostEqual(result["dE_L_dt"].iloc[3], 1.0)

    def test_daily_resampling_uses_right_closed_complete_windows(self):
        times = pd.to_datetime(
            [
                "2020-01-01 06:00",
                "2020-01-01 12:00",
                "2020-01-01 18:00",
                "2020-01-02 00:00",
                "2020-01-02 06:00",
                "2020-01-02 12:00",
                "2020-01-02 18:00",
                "2020-01-03 00:00",
            ]
        )
        frame = pd.DataFrame({"x": np.arange(1.0, 9.0)}, index=times)

        daily = _resample_if_requested(frame, "D")

        self.assertEqual(
            list(daily.index),
            list(pd.to_datetime(["2020-01-02", "2020-01-03"])),
        )
        np.testing.assert_allclose(daily["x"].to_numpy(), [2.5, 6.5])

    def test_daily_resampling_discards_incomplete_windows(self):
        times = pd.to_datetime(
            [
                "2020-01-01 06:00",
                "2020-01-01 12:00",
                "2020-01-01 18:00",
                "2020-01-02 00:00",
                "2020-01-02 12:00",
                "2020-01-02 18:00",
                "2020-01-03 00:00",
            ]
        )
        frame = pd.DataFrame({"x": np.arange(1.0, 8.0)}, index=times)

        daily = _resample_if_requested(frame, "D")

        self.assertEqual(
            list(daily.index),
            list(pd.to_datetime(["2020-01-02"])),
        )

    def test_shared_loader_aligns_daily_interval_means(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)

        lec_times = pd.date_range("2020-01-01 00:00", periods=5, freq="6h")
        lec = pd.DataFrame(
            {
                "time": lec_times,
                "Az": np.arange(5, dtype=float) * 21600.0,
                "Ae": 0.0,
                "Kz": 0.0,
                "Ke": 0.0,
            }
        )
        surface_times = lec_times[1:]
        radiation = pd.DataFrame({"time": surface_times, "Rn": 100.0})
        precipitation = pd.DataFrame({"time": surface_times, "Z": 2.0})

        lec_path = root / "lec.csv"
        radiation_path = root / "radiation.csv"
        precipitation_path = root / "precipitation.csv"
        lec.to_csv(lec_path, index=False)
        radiation.to_csv(radiation_path, index=False)
        precipitation.to_csv(precipitation_path, index=False)

        result = load_interval_analysis(
            lec_path,
            radiation_path,
            precipitation_path,
            frequency="D",
            min_abs_rn=0.5,
        )

        self.assertEqual(
            list(result.index),
            list(pd.to_datetime(["2020-01-02"])),
        )
        self.assertAlmostEqual(result["dE_L_dt"].iloc[0], 1.0)
        self.assertAlmostEqual(result["R_n"].iloc[0], 100.0)
        self.assertAlmostEqual(result["Z"].iloc[0], 2.0)
        self.assertAlmostEqual(result["gamma"].iloc[0], 0.01)

    def test_shared_loader_rejects_irregular_surface_timestamps(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)

        lec_times = pd.date_range("2020-01-01 00:00", periods=5, freq="6h")
        lec = pd.DataFrame(
            {
                "time": lec_times,
                "Az": np.arange(5, dtype=float) * 21600.0,
                "Ae": 0.0,
                "Kz": 0.0,
                "Ke": 0.0,
            }
        )
        surface_times = lec_times[[1, 2, 4]]
        radiation = pd.DataFrame({"time": surface_times, "Rn": 100.0})
        precipitation = pd.DataFrame({"time": lec_times[1:], "Z": 2.0})

        paths = [root / name for name in ("lec.csv", "radiation.csv", "precipitation.csv")]
        lec.to_csv(paths[0], index=False)
        radiation.to_csv(paths[1], index=False)
        precipitation.to_csv(paths[2], index=False)

        with self.assertRaises(ValueError):
            load_interval_analysis(*paths, frequency="D")


    def test_main_alignment_rejects_missing_radiation_timestamps(self):
        times = pd.date_range("2020-01-01 00:00", periods=5, freq="6h")
        lec = pd.DataFrame(
            {
                "dE_L_dt": [np.nan, 1.0, 1.0, 1.0, 1.0],
                "E_L": np.arange(5, dtype=float),
            },
            index=times,
        )
        radiation = pd.DataFrame(
            {"R_n": 100.0},
            index=times[2:],
        )
        with self.assertRaisesRegex(ValueError, "timestamps do not match exactly"):
            from LEC_reproduction import align_energy_and_radiation
            align_energy_and_radiation(lec, radiation)

    def test_main_alignment_rejects_irregular_lec_timestamps(self):
        times = pd.to_datetime(
            ["2020-01-01 00:00", "2020-01-01 06:00", "2020-01-01 18:00"]
        )
        frame = pd.DataFrame(
            {
                "time": times,
                "Az": [0.0, 21600.0, 64800.0],
                "Ae": 0.0,
                "Kz": 0.0,
                "Ke": 0.0,
            }
        )
        with self.assertRaises(ValueError):
            load_lec_results(self._write_lec_csv(frame))

    def test_build_analysis_rejects_missing_precipitation_timestamps(self):
        from LEC_reproduction import build_analysis

        times = pd.date_range("2020-01-01 06:00", periods=4, freq="6h")
        energy_gamma = pd.DataFrame(
            {
                "dE_L_dt": 1.0,
                "R_n": 100.0,
                "gamma": np.linspace(0.01, 0.04, 4),
            },
            index=times,
        )
        precipitation = pd.DataFrame(
            {"Z": [1.0, 2.0, 4.0]},
            index=times[[0, 2, 3]],
        )
        with self.assertRaisesRegex(ValueError, "timestamps"):
            build_analysis(energy_gamma, precipitation)

    def test_conditional_pdf_normalizes_over_nonnegative_precipitation(self):
        from LEC_reproduction import estimate_conditional_pdf

        rng = np.random.default_rng(20261031)
        gamma = rng.normal(0.0, 0.2, 300)
        z = np.maximum(3.0 + 1.5 * gamma + rng.normal(0.0, 0.7, 300), 0.0)
        z_grid, _, conditional, _ = estimate_conditional_pdf(
            gamma, z, gamma_points=40, z_points=160
        )
        integrals = np.trapezoid(conditional, z_grid, axis=0)
        np.testing.assert_allclose(integrals, np.ones_like(integrals), atol=1e-6)


    def test_daily_resampling_rejects_an_interior_missing_day(self):
        times = pd.date_range("2020-01-01 06:00", "2020-01-04 00:00", freq="6h")
        frame = pd.DataFrame({"x": np.arange(len(times), dtype=float)}, index=times)
        frame.loc[times[5], "x"] = np.nan
        with self.assertRaisesRegex(ValueError, "not contiguous"):
            _resample_if_requested(frame, "D")

    def test_shared_daily_windows_reject_an_interior_missing_day(self):
        from temporal_validation import complete_daily_windows

        times = pd.date_range("2020-01-01 06:00", "2020-01-04 00:00", freq="6h")
        frame = pd.DataFrame({"x": np.arange(len(times), dtype=float)}, index=times)
        frame.loc[times[5], "x"] = np.nan
        with self.assertRaisesRegex(ValueError, "not contiguous"):
            complete_daily_windows(frame)


    def test_alignment_preserves_timestamps_with_unstable_radiation(self):
        from LEC_reproduction import align_energy_and_radiation

        times = pd.date_range("2020-01-01 00:00", periods=5, freq="6h")
        lec = pd.DataFrame(
            {"dE_L_dt": [np.nan, 1.0, 1.0, 1.0, 1.0]},
            index=times,
        )
        radiation = pd.DataFrame(
            {"R_n": [100.0, 0.1, 100.0, 100.0]},
            index=times[1:],
        )
        result = align_energy_and_radiation(lec, radiation, min_abs_rn=0.5)
        self.assertEqual(list(result.index), list(times[1:]))
        self.assertTrue(np.isnan(result.loc[times[2], "gamma"]))
        self.assertTrue(np.isfinite(result.loc[times[1], "gamma"]))

    def test_build_analysis_keeps_masked_gamma_timestamps(self):
        from LEC_reproduction import build_analysis

        times = pd.date_range("2020-01-01 06:00", periods=30, freq="6h")
        rng = np.random.default_rng(20261031)
        gamma = rng.normal(0.0, 0.2, len(times))
        gamma[10] = np.nan
        energy_gamma = pd.DataFrame(
            {"dE_L_dt": 1.0, "R_n": 100.0, "gamma": gamma},
            index=times,
        )
        precipitation = pd.DataFrame(
            {"Z": rng.gamma(shape=2.0, scale=1.2, size=len(times))},
            index=times,
        )
        result = build_analysis(energy_gamma, precipitation)
        self.assertEqual(len(result.frame), len(times))
        self.assertTrue(np.isnan(result.frame["gamma"].iloc[10]))
        self.assertTrue(np.isfinite(result.correlation))


    def test_daily_resampling_uses_required_columns_not_optional_diagnostics(self):
        times = pd.date_range("2020-01-01 06:00", periods=4, freq="6h")
        frame = pd.DataFrame(
            {
                "dE_L_dt": [1.0, 2.0, 3.0, 4.0],
                "optional_boundary_term": [1.0, np.nan, 3.0, 4.0],
            },
            index=times,
        )
        daily = _resample_if_requested(
            frame, "D", required_columns=["dE_L_dt"]
        )
        self.assertEqual(len(daily), 1)
        self.assertAlmostEqual(daily["dE_L_dt"].iloc[0], 2.5)
        self.assertAlmostEqual(
            daily["optional_boundary_term"].iloc[0], 8.0 / 3.0
        )


    def test_conditional_cdf_and_exceedance_probabilities_are_normalized(self):
        from LEC_reproduction import conditional_probabilities

        z_grid = np.linspace(0.0, 10.0, 201)
        density = np.column_stack(
            [
                np.exp(-0.5 * ((z_grid - mean) / 1.0) ** 2)
                for mean in (2.0, 4.0, 6.0)
            ]
        )
        density /= np.trapezoid(density, z_grid, axis=0)[np.newaxis, :]
        cdf, exceedance = conditional_probabilities(z_grid, density)

        np.testing.assert_allclose(cdf[0], 0.0)
        np.testing.assert_allclose(cdf[-1], 1.0)
        np.testing.assert_allclose(exceedance, 1.0 - cdf)
        self.assertTrue(np.all(np.diff(cdf, axis=0) >= -1e-12))
        self.assertTrue(np.all((exceedance >= 0.0) & (exceedance <= 1.0)))


    def test_build_analysis_rejects_extra_precipitation_timestamps(self):
        from LEC_reproduction import build_analysis

        times = pd.date_range("2020-01-01 06:00", periods=30, freq="6h")
        rng = np.random.default_rng(31)
        energy_gamma = pd.DataFrame(
            {
                "dE_L_dt": 1.0,
                "R_n": 100.0,
                "gamma": rng.normal(0.0, 0.2, len(times)),
            },
            index=times,
        )
        precipitation = pd.DataFrame(
            {"Z": rng.gamma(2.0, 1.0, len(times) + 1)},
            index=pd.date_range("2020-01-01 00:00", periods=31, freq="6h"),
        )
        with self.assertRaisesRegex(ValueError, "must exactly match"):
            build_analysis(energy_gamma, precipitation)


    def test_exceedance_probabilities_map_to_each_observation_without_extrapolation(self):
        from LEC_reproduction import map_exceedance_to_observations

        times = pd.date_range("2020-01-01", periods=3, freq="D")
        frame = pd.DataFrame(
            {"gamma": [0.5, 1.5, np.nan], "Z": [1.0, 2.0, 3.0]},
            index=times,
        )
        z_grid = np.array([0.0, 5.0])
        gamma_grid = np.array([0.0, 1.0, 2.0])
        exceedance = np.array(
            [[1.0, 0.8, 0.6], [0.0, 0.2, 0.4]]
        )
        result = map_exceedance_to_observations(
            frame, z_grid, gamma_grid, exceedance
        )
        self.assertEqual(len(result), 6)
        self.assertAlmostEqual(
            result.loc[
                (result["time"] == times[0])
                & (result["Z_threshold_mm_day"] == 0.0),
                "P_exceedance_given_gamma",
            ].iloc[0],
            0.9,
        )
        self.assertTrue(
            result.loc[result["time"] == times[2], "P_exceedance_given_gamma"].isna().all()
        )


if __name__ == "__main__":
    unittest.main()
