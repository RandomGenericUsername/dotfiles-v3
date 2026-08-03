from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from icon_templates_renderer.domain.exceptions import (
    ColorSchemeKeyNotFoundError,
    ConfigResolutionError,
    IconRendererError,
    MissingMappingError,
)
from icon_templates_renderer.domain.models import (
    AppSettings,
    ColorScheme,
    ColorSchemeSettings,
    IconGroup,
    OutputSettings,
    ResolvedRoots,
    TemplatesSettings,
    Variant,
    Vocabulary,
)
from icon_templates_renderer.domain.services import (
    MappingResolutionService,
    PathResolutionService,
    PlaceholderSubstitutionService,
)


def _scheme(values: dict[str, str] | None = None) -> ColorScheme:
    return ColorScheme.from_dict(values or {"background": "#1a1a2e", "foreground": "#e0e0e0"})


class TestResolvedRoots:
    def test_defaults_all_none(self) -> None:
        roots = ResolvedRoots()
        assert roots.template_root is None
        assert roots.color_scheme is None
        assert roots.output_root is None

    def test_frozen(self) -> None:
        roots = ResolvedRoots(template_root=Path("/t"))
        with pytest.raises(FrozenInstanceError):
            roots.template_root = Path("/x")


class TestAppSettings:
    def test_defaults(self) -> None:
        s = AppSettings()
        assert s.output.verbosity.value == 1
        assert s.output.output_dir is None
        assert s.templates.dir is None
        assert s.color_scheme.path is None

    def test_construction(self) -> None:
        s = AppSettings(
            output=OutputSettings(output_dir=Path("/o"), verbosity=None),  # type: ignore[arg-type]
            templates=TemplatesSettings(dir=Path("/t")),
            color_scheme=ColorSchemeSettings(path=Path("/c.yaml")),
        )
        assert s.output.output_dir == Path("/o")
        assert s.templates.dir == Path("/t")
        assert s.color_scheme.path == Path("/c.yaml")


class TestIconGroup:
    def test_resolves_mappings_variant_over_group_over_vocab(self) -> None:
        vocab = Vocabulary.from_dict({"k": "v0", "x": "x0"})
        group = IconGroup(
            name="battery",
            template_dir=Path("/t"),
            output_dir=Path("/o"),
            color_mappings={"k": "v1"},
            variants=(
                Variant(
                    name="battery-0",
                    template=Path("/t/a.svg"),
                    output=Path("/o/a.svg"),
                    color_mappings={"k": "v2"},
                ),
            ),
        )
        merged = group.resolve_mappings(group.variants[0], vocab.as_dict())
        assert merged == {"k": "v2", "x": "x0"}

    def test_color_scheme_field_is_absent(self) -> None:
        with pytest.raises(TypeError):
            IconGroup(name="x", color_scheme=Path("/c.yaml"))  # type: ignore[call-arg]

    def test_dirs_default_none(self) -> None:
        g = IconGroup(name="x")
        assert g.template_dir is None
        assert g.output_dir is None


class TestPathResolutionService:
    def setup_method(self) -> None:
        self.service = PathResolutionService()

    def test_join_relative(self) -> None:
        out = self.service.resolve(Path("/root"), "sub/icon.svg")
        assert out == (Path("/root") / "sub/icon.svg").resolve()

    def test_absolute_passthrough(self) -> None:
        out = self.service.resolve(Path("/root"), "/abs/icon.svg")
        assert out == Path("/abs/icon.svg")

    def test_none_root_returns_none(self) -> None:
        assert self.service.resolve(None, "sub/icon.svg") is None

    def test_none_root_with_absolute_returns_none(self) -> None:
        # root None means no resolution context, even absoluteness doesn't restore it.
        assert self.service.resolve(None, "/abs/icon.svg") is None


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


class TestPlaceholderSubstitutionService:
    def setup_method(self) -> None:
        self.service = PlaceholderSubstitutionService()

    def test_substitutes_word_placeholder(self) -> None:
        out = self.service.substitute(
            '<path fill="{{background}}"/>', _scheme(), False, {"background": "background"}
        )
        assert out == '<path fill="#1a1a2e"/>'

    def test_missing_mapping_raises_by_default(self) -> None:
        with pytest.raises(MissingMappingError):
            self.service.substitute("<svg>{{unknown_color}}</svg>", _scheme(), False, {})

    def test_unsafe_leaves_unmapped_verbatim(self) -> None:
        out = self.service.substitute("<svg>{{unknown_color}}</svg>", _scheme(), True, {})
        assert out == "<svg>{{unknown_color}}</svg>"

    def test_hex_literal_bypasses_scheme(self) -> None:
        out = self.service.substitute("{{k}}", _scheme(), False, {"k": "#abcdef"})
        assert out == "#abcdef"

    def test_unknown_scheme_key_raises_by_default(self) -> None:
        with pytest.raises(ColorSchemeKeyNotFoundError):
            self.service.substitute("{{k}}", _scheme(), False, {"k": "missing_key"})

    def test_unsafe_leaves_missing_scheme_key_verbatim(self) -> None:
        out = self.service.substitute("{{k}}", _scheme(), True, {"k": "missing_key"})
        assert out == "{{k}}"


class TestConfigResolutionError:
    def test_message_names_root_and_levers(self) -> None:
        exc = ConfigResolutionError(
            "templates_dir",
            ("--template-dir", "ICON_RENDERER__TEMPLATES__DIR", "[templates] dir", "discovery"),
        )
        msg = str(exc)
        assert "templates_dir" in msg
        assert "--template-dir" in msg
        assert "ICON_RENDERER__TEMPLATES__DIR" in msg
        assert "discovery" in msg

    def test_is_icon_renderer_error(self) -> None:
        exc = ConfigResolutionError("x", ("lever1",))
        assert isinstance(exc, IconRendererError)
