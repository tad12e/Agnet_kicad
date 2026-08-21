"""Client-side data models for KiCad schematic objects.

These are ADAPTER models — lightweight Python representations of objects
that KiCad creates and manages in C++. They are NOT replacements for
KiCad's internal classes (SCH_SYMBOL, SCH_LINE, SCH_JUNCTION, etc.).

KiCad C++ remains the source of truth.
"""

from .component import Component
from .wire import Wire
from .junction import Junction
from .pin import Pin
from .net import Net

__all__ = [
    "Component",
    "Wire",
    "Junction",
    "Pin",
    "Net",
]
