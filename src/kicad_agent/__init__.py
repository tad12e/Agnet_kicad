"""KiCad AI Agent & Automation Framework.

A unified, domain-separated architecture for autonomous KiCad schematic
and PCB design with multi-tiered backend execution and deterministic verification.
"""

from __future__ import annotations

import os
import sys

# Ensure local site-packages and proto paths are available if present
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_LOCAL_SITE = os.path.join(_ROOT, ".site-packages")
_LOCAL_PROTO = os.path.join(_ROOT, "proto")

if os.path.exists(_LOCAL_SITE) and _LOCAL_SITE not in sys.path:
    sys.path.insert(0, _LOCAL_SITE)

if os.path.exists(_LOCAL_PROTO) and _LOCAL_PROTO not in sys.path:
    sys.path.insert(0, _LOCAL_PROTO)

__version__ = "0.2.0"
