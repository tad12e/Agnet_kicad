"""PCB schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class FootprintSchema(BaseModel):
    reference: str
    value: str = ""
    footprint_id: str
    position: Tuple[float, float]
    layer: str = "F.Cu"
    rotation: float = 0.0


class TrackSchema(BaseModel):
    start: Tuple[float, float]
    end: Tuple[float, float]
    width_mm: float = 0.25
    layer: str = "F.Cu"
    net: int = 0
