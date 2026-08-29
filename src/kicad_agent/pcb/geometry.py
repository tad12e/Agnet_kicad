"""Coordinate conversion and geometric utilities for KiCad PCB and Schematics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

NM_PER_MM = 1_000_000


def mm_to_nm(mm: float) -> int:
    """Convert millimeters to nanometers (KiCad internal units)."""
    return int(round(mm * NM_PER_MM))


def nm_to_mm(nm: int) -> float:
    """Convert nanometers to millimeters."""
    return nm / NM_PER_MM


def mm_pair_to_nm(pos: Tuple[float, float]) -> Tuple[int, int]:
    """Convert (X, Y) mm tuple to (X, Y) nm tuple."""
    return mm_to_nm(pos[0]), mm_to_nm(pos[1])


def nm_pair_to_mm(pos: Tuple[int, int]) -> Tuple[float, float]:
    """Convert (X, Y) nm tuple to (X, Y) mm tuple."""
    return nm_to_mm(pos[0]), nm_to_mm(pos[1])


@dataclass
class Point:
    """Represents a 2D coordinate in millimeters."""
    x: float
    y: float

    def distance_to(self, other: Point) -> float:
        """Euclidean distance to another point."""
        return math.hypot(self.x - other.x, self.y - other.y)

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def to_nm(self) -> Tuple[int, int]:
        return mm_pair_to_nm((self.x, self.y))


@dataclass
class BoundingBox:
    """Axis-aligned bounding box."""
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def center(self) -> Point:
        return Point((self.min_x + self.max_x) / 2.0, (self.min_y + self.max_y) / 2.0)

    def contains_point(self, pt: Point) -> bool:
        return self.min_x <= pt.x <= self.max_x and self.min_y <= pt.y <= self.max_y

    def intersects(self, other: BoundingBox) -> bool:
        return not (
            self.max_x < other.min_x
            or self.min_x > other.max_x
            or self.max_y < other.min_y
            or self.min_y > other.max_y
        )
