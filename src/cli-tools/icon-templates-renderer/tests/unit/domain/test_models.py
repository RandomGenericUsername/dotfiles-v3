from __future__ import annotations

from pathlib import Path

from icon_templates_renderer.domain.models import (
    ColorScheme,
    IconGroup,
    Variant,
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
            color_scheme=Path("/c.yaml"),
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
            color_scheme=Path("/c.yaml"),
            template_dir=Path("/t"),
            output_dir=Path("/o"),
            color_mappings={"k": "v1"},
            variants=(),
        )
        variant = Variant(name="battery-0", template=Path("/t/a.svg"), output=Path("/o/a.svg"))
        assert group.resolve_mappings(variant, None) == {"k": "v1"}
