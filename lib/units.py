"""
Unit conversion. The ONE place millimetres become Blender metres.

The datasheet is authored entirely in millimetres because that is how the
engineering references are dimensioned. Blender works in metres. Converting in
exactly one place keeps every module free of scale arithmetic.

    NEVER divide by 1000 inside a build module. Call mm().
"""

from __future__ import annotations

from typing import Iterable

MM: float = 0.001
"""Metres per millimetre."""


def mm(value: float) -> float:
    """Millimetres -> Blender metres."""
    return value * MM


def mmv(*values: float) -> tuple[float, ...]:
    """Convert a run of millimetre values. mmv(100, 200, 50) -> 3-tuple."""
    return tuple(v * MM for v in values)


def mm3(xyz: Iterable[float]) -> tuple[float, float, float]:
    """Convert an (x, y, z) millimetre triple."""
    x, y, z = xyz
    return (x * MM, y * MM, z * MM)


def to_mm(metres: float) -> float:
    """Blender metres -> millimetres. For QA reporting only."""
    return metres / MM
