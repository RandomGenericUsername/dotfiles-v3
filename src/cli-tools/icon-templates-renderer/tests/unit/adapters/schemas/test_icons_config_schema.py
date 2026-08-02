from __future__ import annotations

import pytest
from pydantic import ValidationError

from icon_templates_renderer.adapters.schemas.icons_config_schema import (
    IconGroupSchema,
    VariantSchema,
)


class TestVariantSchema:
    def test_valid(self) -> None:
        v = VariantSchema(name="battery-0", template="battery-0.svg", output="battery-0.svg")
        assert v.name == "battery-0"

    def test_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            VariantSchema(template="a.svg", output="a.svg")


class TestIconGroupSchema:
    def test_valid(self) -> None:
        g = IconGroupSchema(
            color_scheme="colors.yaml",
            template_dir="templates/",
            output_dir="out/",
            variants=[
                VariantSchema(name="battery-0", template="battery-0.svg", output="battery-0.svg")
            ],
        )
        assert g.unsafe is False
        assert g.color_mappings == {}

    def test_missing_variants_raises(self) -> None:
        with pytest.raises(ValidationError):
            IconGroupSchema(
                color_scheme="colors.yaml",
                template_dir="templates/",
                output_dir="out/",
            )

    def test_color_mappings_type_enforced(self) -> None:
        with pytest.raises(ValidationError):
            IconGroupSchema(
                color_scheme="colors.yaml",
                template_dir="templates/",
                output_dir="out/",
                color_mappings="not-a-dict",
                variants=[],
            )
