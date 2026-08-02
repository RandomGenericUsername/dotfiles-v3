from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from icon_templates_renderer.adapters.icon_renderer import IconRenderer
from icon_templates_renderer.domain.exceptions import (
    ColorSchemeNotFoundError,
    IconNotFoundError,
    TemplateNotFoundError,
)
from icon_templates_renderer.domain.models import (
    ColorScheme,
    IconConfig,
    IconGroup,
    ListRequest,
    PathOverrides,
    RenderRequest,
    ValidateRequest,
    Variant,
    Vocabulary,
)


@dataclass
class FakeConfigLoader:
    config: IconConfig
    error: Exception | None = None

    def load(self, yaml_path: Path, overrides: PathOverrides | None = None) -> IconConfig:
        return self.config

    def load_one(
        self, yaml_path: Path, icon: str, overrides: PathOverrides | None = None
    ) -> IconGroup:
        if self.error is not None:
            raise self.error
        for group in self.config.groups:
            if group.name == icon:
                return group
        raise IconNotFoundError(icon, yaml_path)

    def get_resolved_path(self) -> Path | None:
        return None


@dataclass
class FakeColorLoader:
    scheme: ColorScheme
    calls: list[Path] = field(default_factory=list)
    error: Exception | None = None

    def load(self, path: Path) -> ColorScheme:
        self.calls.append(path)
        if self.error is not None:
            raise self.error
        return self.scheme

    def supports(self, path: Path) -> bool:
        return True


@dataclass
class FakeVocabLoader:
    vocab: Vocabulary = field(default_factory=lambda: Vocabulary.from_dict({}))
    calls: list[Path | None] = field(default_factory=list)

    def load(self, path: Path | None) -> Vocabulary:
        self.calls.append(path)
        return self.vocab


@dataclass
class FakeSvgRenderer:
    calls: list[tuple[str, str, bool, dict]] = field(default_factory=list)

    def render_variant(
        self, variant: Variant, scheme: ColorScheme, unsafe: bool, color_mappings: dict[str, str]
    ) -> Path:
        self.calls.append((variant.name, variant.output.name, unsafe, color_mappings))
        variant.output.parent.mkdir(parents=True, exist_ok=True)
        variant.output.write_text("rendered")
        return variant.output

    def render_string(
        self, svg_body: str, scheme: ColorScheme, unsafe: bool, color_mappings: dict[str, str]
    ) -> str:
        return svg_body


def _group(unsafe: bool = False) -> IconGroup:
    return IconGroup(
        name="battery",
        color_scheme=Path("/colors.yaml"),
        template_dir=Path("/templates"),
        output_dir=Path("/tmp/out/battery"),
        unsafe=unsafe,
        variants=(
            Variant(
                name="battery-0",
                template=Path("/templates/battery-0.svg"),
                output=Path("/tmp/out/battery/battery-0.svg"),
            ),
        ),
    )


class TestIconRenderer:
    def test_render_produces_output_paths_in_order(self, tmp_path: Path) -> None:
        group1 = _group()
        group2 = _group()
        group2 = IconGroup(
            name="network",
            color_scheme=Path("/colors.yaml"),
            template_dir=Path("/templates"),
            output_dir=Path("/tmp/out/network"),
            variants=(
                Variant(
                    name="wifi",
                    template=Path("/templates/wifi.svg"),
                    output=Path("/tmp/out/network/wifi.svg"),
                ),
            ),
        )
        svg = FakeSvgRenderer()
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group1, group2))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            svg,
        )
        result = renderer.render(RenderRequest(yaml_path=Path("/icons.yaml")))
        assert result.success
        assert [r.variant_name for r in result.rendered] == ["battery-0", "wifi"]
        assert [r.group_name for r in result.rendered] == ["battery", "network"]

    def test_render_icon_processes_only_named_group(self) -> None:
        group = _group()
        svg = FakeSvgRenderer()
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group,))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            svg,
        )
        result = renderer.render(RenderRequest(yaml_path=Path("/icons.yaml"), icon="battery"))
        assert [r.variant_name for r in result.rendered] == ["battery-0"]

    def test_effective_unsafe_uses_request_value(self) -> None:
        group = _group(unsafe=False)
        svg = FakeSvgRenderer()
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group,))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            svg,
        )
        renderer.render(RenderRequest(yaml_path=Path("/icons.yaml"), unsafe=True))
        assert svg.calls[0][2] is True

    def test_effective_unsafe_falls_back_to_group(self) -> None:
        group = _group(unsafe=True)
        svg = FakeSvgRenderer()
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group,))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            svg,
        )
        renderer.render(RenderRequest(yaml_path=Path("/icons.yaml"), unsafe=None))
        assert svg.calls[0][2] is True

    def test_vocab_default_path_is_yaml_dir_defaults(self) -> None:
        group = _group()
        vocab = FakeVocabLoader()
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group,))),
            FakeColorLoader(ColorScheme.from_dict({})),
            vocab,
            FakeSvgRenderer(),
        )
        renderer.render(RenderRequest(yaml_path=Path("/dir/icons.yaml")))
        assert vocab.calls[0] == Path("/dir/defaults.yaml")

    def test_list_single_icon(self) -> None:
        group = _group()
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group,))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            FakeSvgRenderer(),
        )
        result = renderer.list(ListRequest(yaml_path=Path("/icons.yaml"), icon="battery"))
        assert result.single is True
        assert result.groups == (("battery", ("battery-0",)),)

    def test_validate_passes(self, tmp_path: Path) -> None:
        scheme_file = tmp_path / "c.yaml"
        scheme_file.write_text("special: {}\ncolors: []\n")
        group = IconGroup(
            name="battery",
            color_scheme=scheme_file,
            template_dir=Path("/tmp/t"),
            output_dir=Path("/tmp/o"),
            variants=(),
        )
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group,))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            FakeSvgRenderer(),
        )
        result = renderer.validate(ValidateRequest(yaml_path=Path("/icons.yaml")))
        assert result.ok is True

    def test_validate_missing_color_scheme_raises(self, tmp_path: Path) -> None:
        group = IconGroup(
            name="battery",
            color_scheme=tmp_path / "missing.yaml",
            template_dir=Path("/tmp/t"),
            output_dir=Path("/tmp/o"),
            variants=(),
        )
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group,))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            FakeSvgRenderer(),
        )
        with pytest.raises(ColorSchemeNotFoundError):
            renderer.validate(ValidateRequest(yaml_path=Path("/icons.yaml")))

    def test_validate_missing_template_raises(self, tmp_path: Path) -> None:
        scheme_file = tmp_path / "c.yaml"
        scheme_file.write_text("special: {}\ncolors: []\n")
        group = IconGroup(
            name="battery",
            color_scheme=scheme_file,
            template_dir=Path("/tmp/t"),
            output_dir=Path("/tmp/o"),
            variants=(
                Variant(
                    name="battery-0",
                    template=tmp_path / "missing.svg",
                    output=tmp_path / "out.svg",
                ),
            ),
        )
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group,))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            FakeSvgRenderer(),
        )
        with pytest.raises(TemplateNotFoundError):
            renderer.validate(ValidateRequest(yaml_path=Path("/icons.yaml")))
