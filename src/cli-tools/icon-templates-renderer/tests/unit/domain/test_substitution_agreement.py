from __future__ import annotations

import json
from pathlib import Path

import pytest

from icon_templates_renderer.domain.exceptions import (
    ColorSchemeKeyNotFoundError,
    MissingMappingError,
)
from icon_templates_renderer.domain.models import ColorScheme
from icon_templates_renderer.domain.services import PlaceholderSubstitutionService

_ERRORS = {
    "MissingMappingError": MissingMappingError,
    "ColorSchemeKeyNotFoundError": ColorSchemeKeyNotFoundError,
}


def _fixtures() -> list[dict]:
    """The shared ICME substitution agreement fixture, vendored here.

    The canonical copy lives with the editor in the ags-apps unit
    (`icme/tests/fixtures/substitution.json`). The editor source moved out of
    this repo (slice 7), so the fixture is vendored under this test tree instead
    of being read from `src/gui-tools/icon-color-mapping-editor/`; the two copies
    must stay byte-identical, which is what keeps the Python renderer and the
    TypeScript editor agreeing on placeholder substitution.
    """
    path = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "icme-substitution.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


class TestSubstitutionAgreement:
    @pytest.mark.parametrize("case", _fixtures(), ids=lambda case: case["name"])
    def test_python_service_matches_shared_fixture(self, case: dict) -> None:
        service = PlaceholderSubstitutionService()
        scheme = ColorScheme.from_dict(case["scheme"])
        if case.get("unresolved"):
            with pytest.raises(_ERRORS[case["python_error"]]):
                service.substitute(case["svg"], scheme, False, case["mappings"])
        else:
            assert (
                service.substitute(case["svg"], scheme, False, case["mappings"])
                == case["expected"]
            )
