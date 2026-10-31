"""Tests for ERA5 hourly accumulation processing."""

import unittest

import numpy as np
import pandas as pd

from era5_surface_processing import aggregate_era5_hourly_surface


class Era5SurfaceProcessingTests(unittest.TestCase):
    def _frame(self, periods=13):
        index = pd.date_range("2020-01-01 00:00", periods=periods, freq="h")
        return pd.DataFrame(
            {
                "tsr": 3600.0,
                "ttr": -1800.0,
                "tp": 0.001,
            },
            index=index,
        )

    def test_hourly_accumulations_are_summed_not_differenced(self):
        radiation, precipitation, audit = aggregate_era5_hourly_surface(
            self._frame()
        )
        self.assertEqual(
            list(radiation.index),
            list(pd.to_datetime(["2020-01-01 06:00", "2020-01-01 12:00"])),
        )
        np.testing.assert_allclose(radiation["Rn"], [0.5, 0.5])
        np.testing.assert_allclose(precipitation["Z"], [24.0, 24.0])
        self.assertEqual(audit["complete_six_hour_bins"], 2)
        self.assertEqual(audit["discarded_incomplete_bins"], 1)

    def test_incomplete_variable_bin_is_discarded(self):
        frame = self._frame()
        frame.loc[pd.Timestamp("2020-01-01 03:00"), "ttr"] = np.nan
        radiation, precipitation, audit = aggregate_era5_hourly_surface(frame)
        self.assertEqual(
            list(radiation.index),
            list(pd.to_datetime(["2020-01-01 12:00"])),
        )
        self.assertEqual(list(precipitation.index), list(radiation.index))
        self.assertEqual(audit["complete_six_hour_bins"], 1)

    def test_duplicate_timestamps_are_rejected(self):
        frame = self._frame()
        frame = pd.concat([frame, frame.iloc[[0]]]).sort_index()
        with self.assertRaisesRegex(ValueError, "duplicates"):
            aggregate_era5_hourly_surface(frame)

    def test_off_hour_timestamps_are_rejected(self):
        frame = self._frame()
        frame.index = frame.index + pd.Timedelta(minutes=30)
        with self.assertRaisesRegex(ValueError, "exactly on the hour"):
            aggregate_era5_hourly_surface(frame)

    def test_missing_variables_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing ERA5 surface variables"):
            aggregate_era5_hourly_surface(self._frame().drop(columns=["tp"]))


if __name__ == "__main__":
    unittest.main()
