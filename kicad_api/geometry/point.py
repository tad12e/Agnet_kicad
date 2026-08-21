"""Coordinate conversion and point utilities.

KiCad's coordinate system:
- Internal units: nanometers (nm), stored as int64 in protobuf
- User-facing units: millimeters (mm)
- Conversion: 1 mm = 1,000,000 nm

The protobuf Vector2 message (defined in base_types.proto) uses:
    message Vector2 {
        int64 x_nm = 1;
        int64 y_nm = 2;
    }
"""

from typing import Tuple

# Conversion constant
NM_PER_MM = 1_000_000


def mm_to_nm(mm: float) -> int:
    """Convert millimeters to nanometers (KiCad internal units).

    Args:
        mm: Value in millimeters.

    Returns:
        Value in nanometers as integer.
    """
    return int(round(mm * NM_PER_MM))


def nm_to_mm(nm: int) -> float:
    """Convert nanometers (KiCad internal units) to millimeters.

    Args:
        nm: Value in nanometers.

    Returns:
        Value in millimeters as float.
    """
    return nm / NM_PER_MM


def mm_pair_to_nm(position_mm: Tuple[float, float]) -> Tuple[int, int]:
    """Convert an (x, y) pair from mm to nm.

    Args:
        position_mm: (X, Y) in millimeters.

    Returns:
        (X, Y) in nanometers.
    """
    return mm_to_nm(position_mm[0]), mm_to_nm(position_mm[1])


def nm_pair_to_mm(position_nm: Tuple[int, int]) -> Tuple[float, float]:
    """Convert an (x, y) pair from nm to mm.

    Args:
        position_nm: (X, Y) in nanometers.

    Returns:
        (X, Y) in millimeters.
    """
    return nm_to_mm(position_nm[0]), nm_to_mm(position_nm[1])
