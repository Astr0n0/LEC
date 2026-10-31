"""Unit tests for ERA5 unit and GRIB-step metadata validation."""

import unittest

from era5_metadata import (
    PRESSURE_UNITS,
    SURFACE_UNITS,
    normalize_unit,
    validate_grib_step_types,
    validate_variable_units,
)


class Era5MetadataTests(unittest.TestCase):
    def test_normalizes_common_unit_spellings(self):
        self.assertEqual(normalize_unit("J m**-2"), "jm-2")
        self.assertEqual(normalize_unit("m s-1"), "ms-1")
        self.assertEqual(normalize_unit("m**2 s**-2"), "m2s-2")

    def test_accepts_surface_units(self):
        validate_variable_units(
            {"tp": "m", "tsr": "J m**-2", "ttr": "J m-2"},
            SURFACE_UNITS,
            dataset_label="surface",
        )

    def test_rejects_surface_unit_mismatch(self):
        with self.assertRaisesRegex(ValueError, "unit validation failed"):
            validate_variable_units(
                {"tp": "mm", "tsr": "J m**-2", "ttr": "J m-2"},
                SURFACE_UNITS,
                dataset_label="surface",
            )

    def test_accepts_pressure_level_units(self):
        validate_variable_units(
            {
                "z": "m**2 s**-2",
                "t": "K",
                "u": "m s**-1",
                "v": "m s-1",
                "w": "Pa s**-1",
            },
            PRESSURE_UNITS,
            dataset_label="pressure",
        )

    def test_grib_step_type_validation(self):
        self.assertTrue(
            validate_grib_step_types(
                {"tp": "accum", "tsr": "accum", "ttr": "accum"},
                expected="accum",
                dataset_label="surface",
            )
        )
        self.assertFalse(
            validate_grib_step_types(
                {"tp": None, "tsr": None},
                expected="accum",
                dataset_label="surface",
            )
        )
        with self.assertRaisesRegex(ValueError, "GRIB_stepType"):
            validate_grib_step_types(
                {"tp": "instant"},
                expected="accum",
                dataset_label="surface",
            )


if __name__ == "__main__":
    unittest.main()
