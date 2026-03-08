"""
Conftest for knowledge-base unit/integration tests.

Ensures ``services/knowledge-base/src`` is on sys.path so that
``from app.…`` imports resolve correctly regardless of how pytest
is invoked.
"""

from __future__ import annotations

import pathlib
import sys

_KB_SRC = str(pathlib.Path(__file__).resolve().parents[2] / "services" / "knowledge-base" / "src")

if _KB_SRC not in sys.path:
    sys.path.insert(0, _KB_SRC)
