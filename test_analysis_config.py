"""Tests for automatic selection of the active ERA5 analysis files."""

import tempfile
import unittest
from pathlib import Path

from analysis_config import get_analysis_inputs, get_analysis_timeseries_path


class AnalysisConfigTests(unittest.TestCase):
    def _touch(self, root: Path, relative: str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder", encoding="utf-8")
        return path

    def test_prefers_extended_inputs_when_all_are_available(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extended = (
                self._touch(root, "era5_100d_extended_fixed/paper_lec.csv"),
                self._touch(root, "radiation_100d_extended.csv"),
                self._touch(root, "precipitation_100d_extended.csv"),
            )
            self._touch(root, "era5_100d_fixed/paper_lec.csv")
            self._touch(root, "radiation_100d.csv")
            self._touch(root, "precipitation_100d.csv")
            self.assertEqual(get_analysis_inputs(root), extended)

    def test_falls_back_to_original_inputs_as_a_complete_set(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = (
                self._touch(root, "era5_100d_fixed/paper_lec.csv"),
                self._touch(root, "radiation_100d.csv"),
                self._touch(root, "precipitation_100d.csv"),
            )
            self.assertEqual(get_analysis_inputs(root), original)

    def test_does_not_mix_extended_and_original_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._touch(root, "era5_100d_extended_fixed/paper_lec.csv")
            self._touch(root, "radiation_100d_extended.csv")
            self._touch(root, "precipitation_100d.csv")
            with self.assertRaises(FileNotFoundError):
                get_analysis_inputs(root)

    def test_prefers_extended_analysis_timeseries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = self._touch(root, "LEC_100d_real/analysis_timeseries.csv")
            self.assertEqual(get_analysis_timeseries_path(root), legacy)
            extended = self._touch(
                root, "LEC_100d_extended_analysis/analysis_timeseries.csv"
            )
            self.assertEqual(get_analysis_timeseries_path(root), extended)


if __name__ == "__main__":
    unittest.main()
