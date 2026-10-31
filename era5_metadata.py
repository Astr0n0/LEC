"""Strict unit and GRIB-step metadata checks for ERA5 inputs."""

from __future__ import annotations

import re
from collections.abc import Mapping


SURFACE_UNITS = {
    "tp": {"m", "mofwaterequivalent"},
    "tsr": {"jm-2"},
    "ttr": {"jm-2"},
}
PRESSURE_UNITS = {
    "z": {"m2s-2"},
    "t": {"k"},
    "u": {"ms-1"},
    "v": {"ms-1"},
    "w": {"pas-1"},
}


def normalize_unit(unit: str) -> str:
    """Normalize common CF/GRIB unit spellings without changing dimensions."""
    if not isinstance(unit, str) or not unit.strip():
        raise ValueError("A non-empty units attribute is required.")
    value = unit.strip().lower()
    value = value.replace("metres", "m").replace("meters", "m")
    value = value.replace("metre", "m").replace("meter", "m")
    value = re.sub(r"[\s*^{}()]", "", value)
    return value


def validate_variable_units(
    actual_units: Mapping[str, str],
    expected_units: Mapping[str, set[str]],
    *,
    dataset_label: str,
) -> None:
    """Raise when a required ERA5 variable has missing or incompatible units."""
    errors = []
    for variable, accepted in expected_units.items():
        try:
            actual = normalize_unit(actual_units.get(variable, ""))
        except ValueError:
            errors.append(f"{variable}: missing units; expected one of {sorted(accepted)}")
            continue
        if actual not in accepted:
            errors.append(
                f"{variable}: got {actual_units.get(variable)!r}; "
                f"expected one of {sorted(accepted)}"
            )
    if errors:
        raise ValueError(
            f"{dataset_label} unit validation failed:\n- " + "\n- ".join(errors)
        )


def validate_grib_step_types(
    step_types: Mapping[str, str | None],
    *,
    expected: str,
    dataset_label: str,
) -> bool:
    """Validate GRIB_stepType where present; return False if no attrs are present."""
    present = {
        variable: value.strip().lower()
        for variable, value in step_types.items()
        if isinstance(value, str) and value.strip()
    }
    if not present:
        return False
    wrong = {
        variable: value
        for variable, value in present.items()
        if value != expected.lower()
    }
    if wrong:
        raise ValueError(
            f"{dataset_label} GRIB_stepType must be {expected!r}; got {wrong}."
        )
    return True
