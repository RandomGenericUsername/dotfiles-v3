from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from icon_templates_renderer.adapters.icon_renderer import IconRenderer
from icon_templates_renderer.domain.enums import MappingOrigin
from icon_templates_renderer.domain.exceptions import (
    ColorSchemeNotFoundError,
    ConfigResolutionError,
    IconNotFoundError,
    TemplateNotFoundError,
    UnknownPlaceholderError,
    UnknownTokenError,
)
from icon_templates_renderer.domain.models import (
    ColorScheme,
    IconConfig,
    IconGroup,
    ListRequest,
    MappingSetDefaultRequest,
    MappingSetRequest,
    MappingShowRequest,
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


def _show_roots(tmp_path: Path) -> ResolvedRoots:
    return ResolvedRoots(
        template_root=tmp_path,
        color_scheme=tmp_path / "colors.yaml",
    )


def _show_group(tmp_path: Path) -> IconGroup:
    (tmp_path / "battery-0.svg").write_text('<svg><path fill="{{COLOR_ACCENT}}"/></svg>')
    return IconGroup(
        name="battery",
        template_dir=tmp_path,
        output_dir=tmp_path / "out",
        color_mappings={"COLOR_ACCENT": "color12"},
        variants=(
            Variant(
                name="battery-0",
                template=tmp_path / "battery-0.svg",
                output=tmp_path / "out" / "battery-0.svg",
            ),
            Variant(
                name="battery-50",
                template=tmp_path / "battery-0.svg",
                output=tmp_path / "out" / "battery-50.svg",
                color_mappings={"COLOR_ACCENT": "color3"},
            ),
        ),
    )


def _show_renderer(
    group: IconGroup,
    vocab: Vocabulary | None = None,
    scheme: ColorScheme | None = None,
) -> IconRenderer:
    return IconRenderer(
        FakeConfigLoader(IconConfig(groups=(group,))),
        FakeColorLoader(
            scheme
            if scheme is not None
            else ColorScheme.from_dict({"color12": "#6ea8fe", "color3": "#3f6ea8"})
        ),
        FakeVocabLoader(
            vocab if vocab is not None else Vocabulary.from_dict({"COLOR_FOREGROUND": "foreground"})
        ),
        FakeSvgRenderer(),
    )


class TestIconRendererMappingShow:
    def test_entries_carry_origin(self, tmp_path: Path) -> None:
        group = _show_group(tmp_path)
        renderer = _show_renderer(group)
        result = renderer.mapping_show(
            MappingShowRequest(yaml_path=tmp_path / "icons.yaml", roots=_show_roots(tmp_path))
        )
        assert len(result.groups) == 1
        views = {view.variant: view for view in result.groups[0].variants}
        battery_0 = {entry.placeholder: entry for entry in views["battery-0"].entries}
        assert battery_0["COLOR_ACCENT"].origin is MappingOrigin.GROUP
        assert battery_0["COLOR_ACCENT"].token == "color12"
        assert battery_0["COLOR_FOREGROUND"].origin is MappingOrigin.VOCABULARY
        battery_50 = {entry.placeholder: entry for entry in views["battery-50"].entries}
        assert battery_50["COLOR_ACCENT"].origin is MappingOrigin.VARIANT
        assert battery_50["COLOR_ACCENT"].token == "color3"

    def test_template_bodies_and_paths_present(self, tmp_path: Path) -> None:
        group = _show_group(tmp_path)
        renderer = _show_renderer(group)
        result = renderer.mapping_show(
            MappingShowRequest(yaml_path=tmp_path / "icons.yaml", roots=_show_roots(tmp_path))
        )
        view = result.groups[0].variants[0]
        assert view.template_path == tmp_path / "battery-0.svg"
        assert view.svg_body == '<svg><path fill="{{COLOR_ACCENT}}"/></svg>'

    def test_missing_tokens_collected_not_raised(self, tmp_path: Path) -> None:
        (tmp_path / "battery-0.svg").write_text("<svg/>")
        group = IconGroup(
            name="battery",
            template_dir=tmp_path,
            output_dir=tmp_path / "out",
            color_mappings={"GONE": "surface", "LITERAL": "#ff0066"},
            variants=(
                Variant(
                    name="battery-0",
                    template=tmp_path / "battery-0.svg",
                    output=tmp_path / "out" / "battery-0.svg",
                ),
            ),
        )
        renderer = _show_renderer(group, Vocabulary.from_dict({}))
        result = renderer.mapping_show(
            MappingShowRequest(yaml_path=tmp_path / "icons.yaml", roots=_show_roots(tmp_path))
        )
        assert result.missing_tokens == ("surface",)
        assert result.palette.get("color12") == "#6ea8fe"

    def test_shadows_report_group_and_variant_overrides(self, tmp_path: Path) -> None:
        (tmp_path / "a.svg").write_text("<svg/>")
        (tmp_path / "b.svg").write_text("<svg/>")
        config = IconConfig(
            groups=(
                IconGroup(
                    name="battery",
                    template_dir=tmp_path,
                    output_dir=tmp_path / "out",
                    color_mappings={"COLOR_ACCENT": "color12"},
                    variants=(
                        Variant(
                            name="battery-0",
                            template=tmp_path / "a.svg",
                            output=tmp_path / "out" / "a.svg",
                        ),
                    ),
                ),
                IconGroup(
                    name="network",
                    template_dir=tmp_path,
                    output_dir=tmp_path / "out",
                    variants=(
                        Variant(
                            name="wifi",
                            template=tmp_path / "b.svg",
                            output=tmp_path / "out" / "b.svg",
                            color_mappings={"COLOR_ACCENT": "color3"},
                        ),
                    ),
                ),
            )
        )
        renderer = IconRenderer(
            FakeConfigLoader(config),
            FakeColorLoader(ColorScheme.from_dict({"color12": "#6ea8fe", "color3": "#3f6ea8"})),
            FakeVocabLoader(Vocabulary.from_dict({"COLOR_ACCENT": "foreground"})),
            FakeSvgRenderer(),
        )
        result = renderer.mapping_show(
            MappingShowRequest(yaml_path=tmp_path / "icons.yaml", roots=_show_roots(tmp_path))
        )
        assert result.shadows == (("COLOR_ACCENT", ("battery", "network")),)

    def test_icon_filter_selects_group(self, tmp_path: Path) -> None:
        group = _show_group(tmp_path)
        renderer = _show_renderer(group)
        result = renderer.mapping_show(
            MappingShowRequest(
                yaml_path=tmp_path / "icons.yaml", icon="battery", roots=_show_roots(tmp_path)
            )
        )
        assert [view.group for view in result.groups] == ["battery"]

    def test_unknown_icon_raises(self, tmp_path: Path) -> None:
        group = _show_group(tmp_path)
        renderer = _show_renderer(group)
        with pytest.raises(IconNotFoundError):
            renderer.mapping_show(
                MappingShowRequest(
                    yaml_path=tmp_path / "icons.yaml",
                    icon="nonexistent",
                    roots=_show_roots(tmp_path),
                )
            )

    def test_missing_template_raises(self, tmp_path: Path) -> None:
        group = IconGroup(
            name="battery",
            template_dir=tmp_path,
            output_dir=tmp_path / "out",
            variants=(
                Variant(
                    name="battery-0",
                    template=tmp_path / "absent.svg",
                    output=tmp_path / "out" / "battery-0.svg",
                ),
            ),
        )
        renderer = _show_renderer(group)
        with pytest.raises(TemplateNotFoundError):
            renderer.mapping_show(
                MappingShowRequest(yaml_path=tmp_path / "icons.yaml", roots=_show_roots(tmp_path))
            )

    def test_output_root_not_required(self, tmp_path: Path) -> None:
        group = _show_group(tmp_path)
        renderer = _show_renderer(group)
        roots = ResolvedRoots(
            template_root=tmp_path,
            color_scheme=tmp_path / "colors.yaml",
        )
        result = renderer.mapping_show(
            MappingShowRequest(yaml_path=tmp_path / "icons.yaml", roots=roots)
        )
        assert len(result.groups) == 1

    def test_missing_template_root_raises(self, tmp_path: Path) -> None:
        group = _show_group(tmp_path)
        renderer = _show_renderer(group)
        roots = ResolvedRoots(color_scheme=tmp_path / "colors.yaml")
        with pytest.raises(ConfigResolutionError) as excinfo:
            renderer.mapping_show(
                MappingShowRequest(yaml_path=tmp_path / "icons.yaml", roots=roots)
            )
        assert excinfo.value.name == "templates_dir"

    def test_missing_color_scheme_raises(self, tmp_path: Path) -> None:
        group = _show_group(tmp_path)
        renderer = _show_renderer(group)
        with pytest.raises(ConfigResolutionError) as excinfo:
            renderer.mapping_show(
                MappingShowRequest(
                    yaml_path=tmp_path / "icons.yaml",
                    roots=ResolvedRoots(template_root=tmp_path),
                )
            )
        assert excinfo.value.name == "color_scheme"


def _set_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "icons.yaml"
    path.write_text(
        "battery:\n"
        "  color_mappings:\n"
        "    COLOR_ACCENT: color12\n"
        "  variants:\n"
        "    - name: battery-0\n"
        "      template: battery-0.svg\n"
        "      output: battery-0.svg\n",
        encoding="utf-8",
    )
    return path


def _set_roots(tmp_path: Path) -> ResolvedRoots:
    return ResolvedRoots(color_scheme=tmp_path / "colors.yaml")


def _set_renderer() -> IconRenderer:
    return IconRenderer(
        FakeConfigLoader(IconConfig(groups=())),
        FakeColorLoader(ColorScheme.from_dict({"color12": "#6ea8fe", "color10": "#95d698"})),
        FakeVocabLoader(),
        FakeSvgRenderer(),
    )


class TestIconRendererMappingSet:
    def test_group_set_writes_file(self, tmp_path: Path) -> None:
        manifest = _set_manifest(tmp_path)
        result = _set_renderer().mapping_set(
            MappingSetRequest(
                yaml_path=manifest,
                group="battery",
                placeholder="COLOR_ACCENT",
                token="color10",
                roots=_set_roots(tmp_path),
            )
        )
        assert result.group == "battery"
        assert result.variant is None
        assert result.dry_run is False
        assert "COLOR_ACCENT: color10" in manifest.read_text(encoding="utf-8")

    def test_dry_run_leaves_file_identical(self, tmp_path: Path) -> None:
        manifest = _set_manifest(tmp_path)
        before = manifest.read_text(encoding="utf-8")
        result = _set_renderer().mapping_set(
            MappingSetRequest(
                yaml_path=manifest,
                group="battery",
                placeholder="COLOR_ACCENT",
                token="color10",
                roots=_set_roots(tmp_path),
                dry_run=True,
                show_diff=True,
            )
        )
        assert result.dry_run is True
        assert manifest.read_text(encoding="utf-8") == before
        assert "-    COLOR_ACCENT: color12" in result.diff_text
        assert "+    COLOR_ACCENT: color10" in result.diff_text

    def test_no_diff_by_default(self, tmp_path: Path) -> None:
        manifest = _set_manifest(tmp_path)
        result = _set_renderer().mapping_set(
            MappingSetRequest(
                yaml_path=manifest,
                group="battery",
                placeholder="COLOR_ACCENT",
                token="color10",
                roots=_set_roots(tmp_path),
            )
        )
        assert result.diff_text == ""

    def test_unknown_token_rejected_without_write(self, tmp_path: Path) -> None:
        manifest = _set_manifest(tmp_path)
        before = manifest.read_text(encoding="utf-8")
        with pytest.raises(UnknownTokenError):
            _set_renderer().mapping_set(
                MappingSetRequest(
                    yaml_path=manifest,
                    group="battery",
                    placeholder="COLOR_ACCENT",
                    token="surface",
                    roots=_set_roots(tmp_path),
                )
            )
        assert manifest.read_text(encoding="utf-8") == before

    def test_literal_hex_accepted(self, tmp_path: Path) -> None:
        manifest = _set_manifest(tmp_path)
        _set_renderer().mapping_set(
            MappingSetRequest(
                yaml_path=manifest,
                group="battery",
                placeholder="COLOR_ACCENT",
                token="#ff0066",
                roots=_set_roots(tmp_path),
            )
        )
        assert "COLOR_ACCENT: '#ff0066'" in manifest.read_text(
            encoding="utf-8"
        ) or "COLOR_ACCENT: #ff0066" in manifest.read_text(encoding="utf-8")

    def test_unsafe_allows_unknown_token(self, tmp_path: Path) -> None:
        manifest = _set_manifest(tmp_path)
        _set_renderer().mapping_set(
            MappingSetRequest(
                yaml_path=manifest,
                group="battery",
                placeholder="COLOR_ACCENT",
                token="surface",
                roots=_set_roots(tmp_path),
                unsafe=True,
            )
        )
        assert "COLOR_ACCENT: surface" in manifest.read_text(encoding="utf-8")

    def test_unknown_group_rejected_without_write(self, tmp_path: Path) -> None:
        manifest = _set_manifest(tmp_path)
        before = manifest.read_text(encoding="utf-8")
        with pytest.raises(IconNotFoundError):
            _set_renderer().mapping_set(
                MappingSetRequest(
                    yaml_path=manifest,
                    group="nope",
                    placeholder="K",
                    token="color10",
                    roots=_set_roots(tmp_path),
                )
            )
        assert manifest.read_text(encoding="utf-8") == before

    def test_missing_scheme_root_raises(self, tmp_path: Path) -> None:
        manifest = _set_manifest(tmp_path)
        with pytest.raises(ConfigResolutionError) as excinfo:
            _set_renderer().mapping_set(
                MappingSetRequest(
                    yaml_path=manifest,
                    group="battery",
                    placeholder="K",
                    token="color10",
                )
            )
        assert excinfo.value.name == "color_scheme"


class TestIconRendererMappingSetDefault:
    def _defaults(self, tmp_path: Path) -> Path:
        path = tmp_path / "defaults.yaml"
        path.write_text(
            "defaults:\n  COLOR_ACCENT: accent-muted\n  COLOR_FOREGROUND: foreground\n",
            encoding="utf-8",
        )
        return path

    def _renderer_with_groups(self, groups: tuple[IconGroup, ...]) -> IconRenderer:
        return IconRenderer(
            FakeConfigLoader(IconConfig(groups=groups)),
            FakeColorLoader(ColorScheme.from_dict({"color10": "#95d698"})),
            FakeVocabLoader(),
            FakeSvgRenderer(),
        )

    def test_set_default_writes_and_reports_shadows(self, tmp_path: Path) -> None:
        defaults = self._defaults(tmp_path)
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n  color_mappings:\n    COLOR_ACCENT: color12\n",
            encoding="utf-8",
        )
        group = IconGroup(name="battery", color_mappings={"COLOR_ACCENT": "color12"})
        result = self._renderer_with_groups((group,)).mapping_set_default(
            MappingSetDefaultRequest(
                defaults_path=defaults,
                placeholder="COLOR_ACCENT",
                token="color10",
                icons_path=icons,
                roots=_set_roots(tmp_path),
            )
        )
        assert "COLOR_ACCENT: color10" in defaults.read_text(encoding="utf-8")
        assert result.shadows == ("battery",)

    def test_sibling_manifest_resolved_by_default(self, tmp_path: Path) -> None:
        defaults = self._defaults(tmp_path)
        (tmp_path / "icons.yaml").write_text("x: {}\n", encoding="utf-8")
        group = IconGroup(name="battery", color_mappings={"COLOR_ACCENT": "color12"})
        result = self._renderer_with_groups((group,)).mapping_set_default(
            MappingSetDefaultRequest(
                defaults_path=defaults,
                placeholder="COLOR_FOREGROUND",
                token="color10",
                roots=_set_roots(tmp_path),
            )
        )
        assert result.shadows == ()

    def test_missing_sibling_manifest_gives_empty_shadows(self, tmp_path: Path) -> None:
        defaults = self._defaults(tmp_path)
        group = IconGroup(name="battery", color_mappings={"COLOR_ACCENT": "color12"})
        result = self._renderer_with_groups((group,)).mapping_set_default(
            MappingSetDefaultRequest(
                defaults_path=defaults,
                placeholder="COLOR_ACCENT",
                token="color10",
                roots=_set_roots(tmp_path),
            )
        )
        assert "COLOR_ACCENT: color10" in defaults.read_text(encoding="utf-8")
        assert result.shadows == ()

    def test_unknown_placeholder_rejected_without_write(self, tmp_path: Path) -> None:
        defaults = self._defaults(tmp_path)
        before = defaults.read_text(encoding="utf-8")
        with pytest.raises(UnknownPlaceholderError):
            self._renderer_with_groups(()).mapping_set_default(
                MappingSetDefaultRequest(
                    defaults_path=defaults,
                    placeholder="NOPE",
                    token="color10",
                    roots=_set_roots(tmp_path),
                )
            )
        assert defaults.read_text(encoding="utf-8") == before
