"""Coordinate and geometry utilities for KiCad schematic operations.

KiCad internally uses nanometers (nm) for all coordinates.
The protobuf API uses int64 fields: x_nm, y_nm.
Users work in millimeters (mm).

    1 mm = 1,000,000 nm

This module provides conversion helpers and will eventually handle
rotation transforms and grid snapping for pin position calculations.
"""

from .point import mm_to_nm, nm_to_mm

__all__ = ["mm_to_nm", "nm_to_mm"]
