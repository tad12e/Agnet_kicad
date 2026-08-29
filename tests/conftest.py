"""Pytest configuration and global test fixtures."""

import os
import sys
import pytest

# Ensure workspace paths are on sys.path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC = os.path.join(_ROOT, "src")
_SITE_PACKAGES = os.path.join(_ROOT, ".site-packages")
_PROTO = os.path.join(_ROOT, "proto")

for path in [_SITE_PACKAGES, _SRC, _PROTO, _ROOT]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

# Inject mock_pcbnew for deterministic offline unit testing
from tests import mock_pcbnew
sys.modules["pcbnew"] = mock_pcbnew


@pytest.fixture(autouse=True)
def reset_mock_board():
    """Reset mock_pcbnew board instance before each test."""
    mock_pcbnew.ResetBoard()
    yield
    mock_pcbnew.ResetBoard()


@pytest.fixture
def sample_pcb_file():
    """Return path to sample fixture PCB file."""
    return os.path.join(_ROOT, "tests", "fixtures", "pcb", "simple_board.kicad_pcb")


@pytest.fixture
def sample_sch_file():
    """Return path to sample fixture schematic file."""
    return os.path.join(_ROOT, "tests", "fixtures", "schematic", "simple_schematic.kicad_sch")
