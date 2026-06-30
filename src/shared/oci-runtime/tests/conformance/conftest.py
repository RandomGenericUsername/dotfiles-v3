"""Conformance test configuration.

Warns when conformance fixtures are missing or empty — run
``make capture-fixtures`` to regenerate them.
"""

import warnings
from pathlib import Path

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def pytest_configure(config):
    missing = []
    for runtime_dir in (_FIXTURE_DIR / "docker", _FIXTURE_DIR / "podman"):
        if not runtime_dir.is_dir():
            missing.append(runtime_dir.name)
            continue
        if not any(runtime_dir.iterdir()):
            missing.append(runtime_dir.name)
    if missing:
        warnings.warn(
            f"Conformance fixtures missing for: {', '.join(missing)}. "
            f"Run 'make capture-fixtures' to generate them.",
            stacklevel=2,
        )
