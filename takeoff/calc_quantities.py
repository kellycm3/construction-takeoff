"""Plain geometry and ordering math. No AI here."""
import math
from typing import Optional


def studs_for_run(length_ft: float, spacing_in: float) -> int:
    """Studs at spacing along a wall, plus the closing stud."""
    return math.ceil(length_ft * 12 / spacing_in) + 1


def slope_factor(pitch: float) -> float:
    return math.sqrt(1 + (pitch / 12) ** 2)


def rafter_length_ft(half_span_ft: float, overhang_in: float, pitch: float) -> float:
    return (half_span_ft + overhang_in / 12) * slope_factor(pitch)


def gable_roof_area_sf(length_ft: float, width_ft: float, pitch: float, eave_in: float, rake_in: float) -> float:
    slope_len = rafter_length_ft(width_ft / 2, eave_in, pitch)
    return 2 * slope_len * (length_ft + 2 * rake_in / 12)


def gable_rise_ft(width_ft: float, pitch: float) -> float:
    return (width_ft / 2) * pitch / 12


def gable_area_sf(width_ft: float, height_ft: float) -> float:
    """Triangle area of one gable end."""
    return 0.5 * width_ft * height_ft


def order_units(measure: float, waste: float, coverage_per_unit: float) -> int:
    """Apply waste to the MEASUREMENT, then convert to orderable units."""
    if coverage_per_unit <= 0:
        raise ValueError("coverage_per_unit must be > 0")
    return math.ceil(round(measure * (1 + waste) / coverage_per_unit, 6))


def raw_units(measure: float, coverage_per_unit: float) -> int:
    return math.ceil(round(measure / coverage_per_unit, 6))


def ice_barrier_courses(overhang_in: float, pitch: float, inside_wall_in: float, roll_width_in: float) -> int:
    """How many rows of ice & water barrier are needed up the slope from the eave."""
    up_slope_in = (overhang_in + inside_wall_in) * slope_factor(pitch)
    return math.ceil(up_slope_in / roll_width_in)


def bigger_nominal(nominal: str) -> Optional[str]:
    """2x6 -> 2x8, used for ridge boards."""
    order = ["2x4", "2x6", "2x8", "2x10", "2x12"]
    if nominal in order and order.index(nominal) < len(order) - 1:
        return order[order.index(nominal) + 1]
    return None
