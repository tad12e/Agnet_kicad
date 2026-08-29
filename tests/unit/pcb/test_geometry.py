"""Unit tests for PCB geometry and coordinate conversion."""

from kicad_agent.pcb.geometry import (
    BoundingBox,
    Point,
    mm_pair_to_nm,
    mm_to_nm,
    nm_pair_to_mm,
    nm_to_mm,
)


def test_mm_nm_conversions():
    assert mm_to_nm(1.0) == 1_000_000
    assert mm_to_nm(0.5) == 500_000
    assert nm_to_mm(1_000_000) == 1.0
    assert nm_to_mm(500_000) == 0.5


def test_pair_conversions():
    nm_pair = mm_pair_to_nm((12.5, 34.75))
    assert nm_pair == (12_500_000, 34_750_000)
    mm_pair = nm_pair_to_mm(nm_pair)
    assert mm_pair == (12.5, 34.75)


def test_point_and_bounding_box():
    p1 = Point(0, 0)
    p2 = Point(3, 4)
    assert p1.distance_to(p2) == 5.0

    bbox1 = BoundingBox(0, 0, 10, 10)
    bbox2 = BoundingBox(5, 5, 15, 15)
    bbox3 = BoundingBox(20, 20, 30, 30)

    assert bbox1.contains_point(Point(5, 5))
    assert not bbox1.contains_point(Point(15, 15))
    assert bbox1.intersects(bbox2)
    assert not bbox1.intersects(bbox3)
