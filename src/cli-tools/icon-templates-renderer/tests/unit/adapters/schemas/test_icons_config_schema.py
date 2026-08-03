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
    def test_valid_with_default_dirs(self) -> None:
        g = IconGroupSchema(
            variants=[
                VariantSchema(name="battery-0", template="battery-0.svg", output="battery-0.svg")
            ],
        )
        assert g.unsafe is False
        assert g.color_mappings == {}
        assert g.template_dir == "."
        assert g.output_dir == "."

    def test_missing_variants_raises(self) -> None:
        with pytest.raises(ValidationError):
            IconGroupSchema(
                template_dir="templates/",
                output_dir="out/",
            )

    def test_color_mappings_type_enforced(self) -> None:
        with pytest.raises(ValidationError):
            IconGroupSchema(
                template_dir="templates/",
                output_dir="out/",
                color_mappings="not-a-dict",
                variants=[],
            )

    def test_relative_subdir_dirs(self) -> None:
        g = IconGroupSchema(
            template_dir="sub/",
            output_dir="out/battery/",
            variants=[
                VariantSchema(name="battery-0", template="battery-0.svg", output="battery-0.svg")
            ],
        )
        assert g.template_dir == "sub/"
        assert g.output_dir == "out/battery/"

    def test_color_scheme_field_is_removed(self) -> None:
        g = IconGroupSchema(
            color_scheme="colors.yaml",  # type: ignore[call-arg]
            template_dir="templates/",
            output_dir="out/",
            variants=[],
        )
        assert not hasattr(g, "color_scheme")
