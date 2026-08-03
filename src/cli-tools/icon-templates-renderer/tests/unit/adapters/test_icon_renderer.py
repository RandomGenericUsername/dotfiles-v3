from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from icon_templates_renderer.adapters.icon_renderer import IconRenderer
from icon_templates_renderer.domain.exceptions import (
    ColorSchemeNotFoundError,
    ConfigResolutionError,
    IconNotFoundError,
    TemplateNotFoundError,
)
from icon_templates_renderer.domain.models import (
    ColorScheme,
    IconConfig,
    IconGroup,
    ListRequest,
    RenderRequest,
    ResolvedRoots,
    ValidateRequest,
    Variant,
    Vocabulary,
)


@dataclass
class FakeConfigLoader:
    config: IconConfig
    error: Exception | None = None

    def load(self, yaml_path: Path, roots: ResolvedRoots | None = None) -> IconConfig:
        return self.config

    def load_one(self, yaml_path: Path, icon: str, roots: ResolvedRoots | None = None) -> IconGroup:
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


def _roots() -> ResolvedRoots:
    return ResolvedRoots(
        template_root=Path("/templates"),
        color_scheme=Path("/colors.yaml"),
        output_root=Path("/tmp/out"),
    )


def _group(unsafe: bool = False, name: str = "battery") -> IconGroup:
    return IconGroup(
        name=name,
        template_dir=Path("/templates"),
        output_dir=Path(f"/tmp/out/{name}"),
        unsafe=unsafe,
        variants=(
            Variant(
                name="battery-0",
                template=Path("/templates/battery-0.svg"),
                output=Path(f"/tmp/out/{name}/battery-0.svg"),
            ),
        ),
    )


class TestIconRenderer:
    def test_render_produces_output_paths_in_order(self, tmp_path: Path) -> None:
        group1 = _group()
        group2 = _group(name="network")
        svg = FakeSvgRenderer()
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group1, group2))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            svg,
        )
        result = renderer.render(RenderRequest(yaml_path=Path("/icons.yaml"), roots=_roots()))
        assert result.success
        assert [r.variant_name for r in result.rendered] == ["battery-0", "battery-0"]
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
        result = renderer.render(
            RenderRequest(yaml_path=Path("/icons.yaml"), icon="battery", roots=_roots())
        )
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
        renderer.render(RenderRequest(yaml_path=Path("/icons.yaml"), unsafe=True, roots=_roots()))
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
        renderer.render(RenderRequest(yaml_path=Path("/icons.yaml"), unsafe=None, roots=_roots()))
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
        renderer.render(RenderRequest(yaml_path=Path("/dir/icons.yaml"), roots=_roots()))
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

    def test_list_tolerates_none_roots(self) -> None:
        group = _group()
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group,))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            FakeSvgRenderer(),
        )
        result = renderer.list(ListRequest(yaml_path=Path("/icons.yaml")))
        assert result.groups == (("battery", ("battery-0",)),)

    def test_validate_passes(self, tmp_path: Path) -> None:
        scheme_file = tmp_path / "c.yaml"
        scheme_file.write_text("special: {}\ncolors: []\n")
        template_file = tmp_path / "t.svg"
        template_file.write_text("<svg/>")
        group = IconGroup(
            name="battery",
            template_dir=tmp_path,
            output_dir=tmp_path / "o",
            variants=(
                Variant(
                    name="battery-0",
                    template=template_file,
                    output=tmp_path / "o" / "battery-0.svg",
                ),
            ),
        )
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group,))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            FakeSvgRenderer(),
        )
        roots = ResolvedRoots(
            template_root=tmp_path,
            color_scheme=scheme_file,
            output_root=tmp_path / "o",
        )
        result = renderer.validate(ValidateRequest(yaml_path=Path("/icons.yaml"), roots=roots))
        assert result.ok is True

    def test_validate_missing_color_scheme_raises(self, tmp_path: Path) -> None:
        group = _group()
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group,))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            FakeSvgRenderer(),
        )
        roots = ResolvedRoots(
            template_root=tmp_path,
            color_scheme=tmp_path / "missing.yaml",
            output_root=tmp_path,
        )
        with pytest.raises(ColorSchemeNotFoundError):
            renderer.validate(ValidateRequest(yaml_path=Path("/icons.yaml"), roots=roots))

    def test_validate_missing_template_raises(self, tmp_path: Path) -> None:
        scheme_file = tmp_path / "c.yaml"
        scheme_file.write_text("special: {}\ncolors: []\n")
        group = IconGroup(
            name="battery",
            template_dir=tmp_path,
            output_dir=tmp_path / "o",
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
        roots = ResolvedRoots(
            template_root=tmp_path,
            color_scheme=scheme_file,
            output_root=tmp_path / "o",
        )
        with pytest.raises(TemplateNotFoundError):
            renderer.validate(ValidateRequest(yaml_path=Path("/icons.yaml"), roots=roots))

    def test_render_requires_roots(self) -> None:
        group = _group()
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group,))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            FakeSvgRenderer(),
        )
        with pytest.raises(ConfigResolutionError) as excinfo:
            renderer.render(RenderRequest(yaml_path=Path("/icons.yaml")))
        assert excinfo.value.name == "templates_dir"

    def test_validate_requires_roots(self) -> None:
        group = _group()
        renderer = IconRenderer(
            FakeConfigLoader(IconConfig(groups=(group,))),
            FakeColorLoader(ColorScheme.from_dict({})),
            FakeVocabLoader(),
            FakeSvgRenderer(),
        )
        with pytest.raises(ConfigResolutionError) as excinfo:
            renderer.validate(ValidateRequest(yaml_path=Path("/icons.yaml")))
        assert excinfo.value.name == "templates_dir"
