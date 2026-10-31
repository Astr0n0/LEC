"""Tests for publishing LorenzCycleToolkit output at a stable path."""

import tempfile
import unittest
from pathlib import Path

from LEC_reproduction import _publish_toolkit_result


class ToolkitOutputTests(unittest.TestCase):
    def test_toolkit_csv_is_copied_to_canonical_location(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            atmospheric = root / "era5_100d_extended.nc"
            atmospheric.touch()
            toolkit_output = (
                root / "analysis" / "toolkit_work" / "LEC_Results"
                / "era5_100d_extended_fixed" / "paper_lec.csv"
            )
            toolkit_output.parent.mkdir(parents=True)
            toolkit_output.write_text("time,Az\n2020-01-01,1\n", encoding="utf-8")

            result = _publish_toolkit_result(
                toolkit_output, atmospheric, "paper_lec"
            )

            self.assertEqual(
                result,
                root / "era5_100d_extended_fixed" / "paper_lec.csv",
            )
            self.assertEqual(result.read_text(encoding="utf-8"), toolkit_output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
