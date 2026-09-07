from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from icon_templates_renderer.domain.enums import MappingOrigin
from icon_templates_renderer.domain.models import (
    ColorScheme,
    GroupMappingView,
    IconGroup,
    MappingEntry,
    MappingShowRequest,
    MappingShowResult,
    ResolvedRoots,
    Variant,
    VariantMappingView,
    Vocabulary,
)


class TestColorScheme:
    def test_from_dict_and_get(self) -> None:
        scheme = ColorScheme.from_dict({"background": "#1a1a2e", "color1": "#e94560"})
        assert scheme.get("background") == "#1a1a2e"
        assert scheme.get("color1") == "#e94560"
        assert scheme.get("missing") is None


class TestIconGroupResolveMappings:
    def test_priority_variant_over_group_over_vocab(self) -> None:
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
        variant = group.variants[0]
        merged = group.resolve_mappings(variant, vocab.as_dict())
        assert merged == {"k": "v2", "x": "x0"}

    def test_vocab_defaults_none(self) -> None:
        group = IconGroup(
            name="battery",
            template_dir=Path("/t"),
            output_dir=Path("/o"),
            color_mappings={"k": "v1"},
            variants=(),
        )
        variant = Variant(name="battery-0", template=Path("/t/a.svg"), output=Path("/o/a.svg"))
        assert group.resolve_mappings(variant, None) == {"k": "v1"}


class TestMappingOrigin:
    def test_values(self) -> None:
        assert MappingOrigin.VOCABULARY.value == "vocabulary"
        assert MappingOrigin.GROUP.value == "group"
        assert MappingOrigin.VARIANT.value == "variant"


class TestMappingEntry:
    def test_fields(self) -> None:
        entry = MappingEntry(
            placeholder="COLOR_ACCENT", token="color12", origin=MappingOrigin.GROUP
        )
        assert entry.placeholder == "COLOR_ACCENT"
        assert entry.token == "color12"
        assert entry.origin is MappingOrigin.GROUP

    def test_frozen(self) -> None:
        entry = MappingEntry(placeholder="K", token="v", origin=MappingOrigin.VARIANT)
        with pytest.raises(FrozenInstanceError):
            entry.token = "other"  # type: ignore[misc]


class TestVariantMappingView:
    def test_defaults(self) -> None:
        view = VariantMappingView(
            variant="battery-50", template_path=Path("/t/icon.svg"), svg_body="<svg/>"
        )
        assert view.entries == ()
        assert view.svg_body == "<svg/>"


class TestGroupMappingView:
    def test_defaults(self) -> None:
        view = GroupMappingView(group="battery")
        assert view.variants == ()


class TestMappingShowRequest:
    def test_defaults(self) -> None:
        request = MappingShowRequest(yaml_path=Path("/c/icons.yaml"))
        assert request.icon is None
        assert request.roots == ResolvedRoots()
        assert request.vocabulary_path is None


class TestMappingShowResult:
    def test_defaults(self) -> None:
        result = MappingShowResult()
        assert result.groups == ()
        assert result.palette.get("anything") is None
        assert result.missing_tokens == ()
        assert result.shadows == ()
