"""Unit tests for kicad_api.geometry."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kicad_api.geometry import mm_to_nm, nm_to_mm
from kicad_api.geometry.point import mm_pair_to_nm, nm_pair_to_mm


def test_mm_to_nm():
    assert mm_to_nm(1.0) == 1_000_000
    assert mm_to_nm(0.5) == 500_000
    assert mm_to_nm(100.0) == 100_000_000
    assert mm_to_nm(0.0) == 0


def test_nm_to_mm():
    assert nm_to_mm(1_000_000) == 1.0
    assert nm_to_mm(500_000) == 0.5
    assert nm_to_mm(100_000_000) == 100.0
    assert nm_to_mm(0) == 0.0


def test_pair_conversions():
    nm_pair = mm_pair_to_nm((12.5, 34.75))
    assert nm_pair == (12_500_000, 34_750_000)
    mm_pair = nm_pair_to_mm(nm_pair)
    assert mm_pair == (12.5, 34.75)
