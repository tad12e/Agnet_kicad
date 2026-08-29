"""Schematic schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class SymbolSchema(BaseModel):
    lib_id: str
    reference: str
    value: str = ""
    position: Tuple[float, float]
    rotation: float = 0.0


class WireSchema(BaseModel):
    start: Tuple[float, float]
    end: Tuple[float, float]
