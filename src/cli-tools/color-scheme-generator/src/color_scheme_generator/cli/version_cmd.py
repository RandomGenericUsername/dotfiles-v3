from __future__ import annotations

import json
from importlib.metadata import version as _pkg_version


def version() -> None:
    ver = _pkg_version("color-scheme-generator")
    print(json.dumps({"version": ver}))
