"""Unit tests for interval-ending LEC/radiation temporal alignment."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from LEC_reproduction import _resample_if_requested, load_lec_results


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


if __name__ == "__main__":
    unittest.main()
