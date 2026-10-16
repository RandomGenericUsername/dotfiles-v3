"""Make `btop_live` importable when pytest runs from the studio root.

pytest's default import mode prepends the TEST file's directory (`live/tests`),
not `live/`, so the engine module next door would not be importable. This
conftest adds the `live/` dir (its own parent) to sys.path.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
