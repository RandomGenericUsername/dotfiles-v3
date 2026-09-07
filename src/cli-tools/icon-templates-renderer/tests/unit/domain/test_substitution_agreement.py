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


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "src" / "gui-tools").is_dir():
            return parent
    raise AssertionError("repository root (with src/gui-tools/) not found")


def _fixtures() -> list[dict]:
    path = (
        _repo_root()
        / "src"
        / "gui-tools"
        / "icon-color-mapping-editor"
        / "tests"
        / "fixtures"
        / "substitution.json"
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
