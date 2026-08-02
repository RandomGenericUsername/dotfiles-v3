from __future__ import annotations

from pathlib import Path

import pytest

from icon_templates_renderer.domain.exceptions import (
    ColorSchemeKeyNotFoundError,
    MissingMappingError,
)
from icon_templates_renderer.domain.models import ColorScheme, PathOverrides
from icon_templates_renderer.domain.services import (
    MappingResolutionService,
    PathResolutionService,
    PlaceholderSubstitutionService,
)


def _scheme(values: dict[str, str] | None = None) -> ColorScheme:
    return ColorScheme.from_dict(values or {"background": "#1a1a2e", "foreground": "#e0e0e0"})


class TestPlaceholderSubstitutionService:
    def setup_method(self) -> None:
        self.service = PlaceholderSubstitutionService()

    def test_word_characters_are_matched(self) -> None:
        out = self.service.substitute(
            '<path fill="{{background}}"/>', _scheme(), False, {"background": "background"}
        )
        assert out == '<path fill="#1a1a2e"/>'

    def test_non_placeholder_text_is_preserved(self) -> None:
        out = self.service.substitute(
            "<svg>{{a}} text {{b}}</svg>",
            _scheme(),
            False,
            {"a": "#111111", "b": "#222222"},
        )
        assert out == "<svg>#111111 text #222222</svg>"

    def test_missing_mapping_raises_by_default(self) -> None:
        with pytest.raises(MissingMappingError) as excinfo:
            self.service.substitute("<svg>{{unknown_color}}</svg>", _scheme(), False, {})
        assert "Placeholder '{{unknown_color}}' has no entry in color_mappings" in str(
            excinfo.value
        )

    def test_unsafe_leaves_unmapped_placeholder_verbatim(self) -> None:
        out = self.service.substitute("<svg>{{unknown_color}}</svg>", _scheme(), True, {})
        assert out == "<svg>{{unknown_color}}</svg>"

    def test_hex_literal_bypasses_scheme(self) -> None:
        out = self.service.substitute("{{k}}", _scheme(), False, {"k": "#abcdef"})
        assert out == "#abcdef"

    def test_scheme_key_resolves(self) -> None:
        out = self.service.substitute("{{k}}", _scheme(), False, {"k": "background"})
        assert out == "#1a1a2e"

    def test_unknown_scheme_key_raises_by_default(self) -> None:
        with pytest.raises(ColorSchemeKeyNotFoundError) as excinfo:
            self.service.substitute("{{k}}", _scheme(), False, {"k": "missing_key"})
        assert "references color scheme key 'missing_key' which does not exist" in str(
            excinfo.value
        )

    def test_unsafe_leaves_missing_scheme_key_verbatim(self) -> None:
        out = self.service.substitute("{{k}}", _scheme(), True, {"k": "missing_key"})
        assert out == "{{k}}"


class TestPathResolutionService:
    def setup_method(self) -> None:
        self.service = PathResolutionService()
        self.base = Path("/tmp/yaml")

    def test_template_dir_cli_override_joins(self) -> None:
        overrides = PathOverrides(template_dir=Path("/new/templates"))
        out = self.service.resolve_template_dir(self.base, "battery/", overrides, None)
        assert out == Path("/new/templates/battery/")

    def test_template_dir_top_level_root_used(self) -> None:
        out = self.service.resolve_template_dir(
            self.base, "battery/", PathOverrides(), Path("/root/tpls")
        )
        assert out == Path("/root/tpls/battery/")

    def test_template_dir_relative_to_yaml_dir(self) -> None:
        out = self.service.resolve_template_dir(
            self.base, "templates/battery/", PathOverrides(), None
        )
        assert out == self.base / "templates/battery/"

    def test_color_scheme_override_replaces_whole(self) -> None:
        overrides = PathOverrides(color_scheme=Path("/new/colors.yaml"))
        out = self.service.resolve_color_scheme(self.base, "ignored.yaml", overrides, None)
        assert out == Path("/new/colors.yaml")

    def test_color_scheme_top_level_global_used(self) -> None:
        out = self.service.resolve_color_scheme(
            self.base, "ignored.yaml", PathOverrides(), Path("/global/colors.yaml")
        )
        assert out == Path("/global/colors.yaml")

    def test_output_dir_cli_override_joins(self) -> None:
        overrides = PathOverrides(output_dir=Path("/new/out"))
        out = self.service.resolve_output_dir(self.base, "battery/", overrides, None)
        assert out == Path("/new/out/battery/")

    def test_absolute_paths_pass_through(self) -> None:
        out = self.service.resolve(self.base, "/abs/battery/")
        assert out == Path("/abs/battery/")


class TestMappingResolutionService:
    def setup_method(self) -> None:
        self.service = MappingResolutionService()

    def test_variant_overrides_group(self) -> None:
        out = self.service.merge({"k": "v0"}, {"k": "v1", "g": "gv"}, {"k": "v2"})
        assert out == {"k": "v2", "g": "gv"}

    def test_group_overrides_vocab(self) -> None:
        out = self.service.merge({"k": "v0"}, {"k": "v1"}, {})
        assert out == {"k": "v1"}

    def test_vocab_fills_when_neither_overrides(self) -> None:
        out = self.service.merge({"k": "v0", "x": "x0"}, {"k": "v1"}, {})
        assert out == {"k": "v1", "x": "x0"}
