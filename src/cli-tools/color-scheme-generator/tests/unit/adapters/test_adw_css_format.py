from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from color_scheme_generator.adapters.jinja_template_renderer import JinjaTemplateRenderer
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.models import Color, ColorScheme

_DEFINE_COLOR_RE = re.compile(
    r"@define-color (?P<name>[A-Za-z0-9_]+) (?P<value>.+?);"
)
_PASSTHROUGH_RE = re.compile(r"@define-color color_[0-9]{2} #[0-9a-fA-F]{6};")

# AC-2 pinned §5 mapping: named color -> palette slot. Literal dict so template
# drift fails loudly. Passthrough color_NN entries are appended below.
_NAMED_COLOR_SLOTS: dict[str, str] = {
    "window_bg_color": "background",
    "view_bg_color": "background",
    "headerbar_bg_color": "mix:colors[2]:55%",
    "card_bg_color": "mix:colors[3]:35%",
    "dialog_bg_color": "background",
    "dialog_fg_color": "foreground",
    "popover_bg_color": "mix:colors[1]:45%",
    "popover_fg_color": "foreground",
    "sidebar_bg_color": "mix:colors[1]:45%",
    "window_fg_color": "foreground",
    "view_fg_color": "foreground",
    "headerbar_fg_color": "foreground",
    "card_fg_color": "foreground",
    "sidebar_fg_color": "foreground",
    "accent_color": "colors[4]",
    "accent_bg_color": "colors[4]",
    "accent_fg_color": "background",
    "destructive_color": "colors[8]",
    "destructive_bg_color": "colors[8]",
    "destructive_fg_color": "background",
    "success_color": "colors[6]",
    "success_bg_color": "colors[6]",
    "success_fg_color": "background",
    "warning_color": "colors[12]",
    "warning_bg_color": "colors[12]",
    "warning_fg_color": "background",
    "error_color": "colors[9]",
    "error_bg_color": "colors[9]",
    "error_fg_color": "background",
}

_EXPECTED_SLOTS: dict[str, str] = {
    **_NAMED_COLOR_SLOTS,
    **{f"color_{i:02d}": f"colors[{i}]" for i in range(16)},
}


class _BundledDirResolver:
    def __init__(self, templates_dir: Path) -> None:
        self._templates_dir = templates_dir

    def resolve(self, settings_dir: Path | None = None) -> Path:
        return self._templates_dir


@pytest.fixture
def _bundled_templates_dir() -> Path:
    pkg_dir = Path(__file__).resolve().parent.parent.parent.parent
    return pkg_dir / "src" / "color_scheme_generator" / "defaults" / "templates"


@pytest.fixture
def _scheme() -> ColorScheme:
    colors = tuple(Color("#%06x" % (i * 0x111111), (i * 17, i * 17, i * 17)) for i in range(16))
    return ColorScheme(
        background=Color("#1a1b26", (26, 27, 38)),
        foreground=Color("#c0caf5", (192, 202, 245)),
        cursor=Color("#f7768e", (247, 118, 142)),
        colors=colors,
        source_image=Path("/tmp/test.png"),
        backend=Backend.CUSTOM,
        generated_at=datetime(2024, 1, 1),
    )


def _slot_hex(scheme: ColorScheme, slot: str) -> str:
    if slot == "background":
        return scheme.background.hex
    if slot == "foreground":
        return scheme.foreground.hex
    if slot.startswith("mix:"):
        # "mix:colors[N]:P%" -> color-mix(in srgb, #N-hex P%, #bg-hex);
        _, source, pct = slot.split(":")
        idx = int(source[len("colors[") : -1])
        return (
            f"color-mix(in srgb, {scheme.colors[idx].hex} {pct}, {scheme.background.hex})"
        )
    index = int(slot[len("colors[") : -1])
    return scheme.colors[index].hex


def _parse_define_colors(content: str) -> dict[str, str]:
    return {
        m.group("name"): m.group("value").strip()
        for m in _DEFINE_COLOR_RE.finditer(content)
    }


class TestAdwCssFormat:
    def test_render_named_color_completeness_matches_pinned_mapping(
        self, _bundled_templates_dir: Path, _scheme: ColorScheme, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "colors.adw.css"
        renderer = JinjaTemplateRenderer(_BundledDirResolver(_bundled_templates_dir))
        renderer.render("colors.adw.css.j2", _scheme, output_path)

        content = output_path.read_text()
        defined = _parse_define_colors(content)

        assert set(defined) == set(_EXPECTED_SLOTS)
        for name, slot in _EXPECTED_SLOTS.items():
            assert defined[name] == _slot_hex(_scheme, slot), f"{name} <- {slot}"

    def test_render_has_no_extra_define_color_lines(
        self, _bundled_templates_dir: Path, _scheme: ColorScheme, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "colors.adw.css"
        renderer = JinjaTemplateRenderer(_BundledDirResolver(_bundled_templates_dir))
        renderer.render("colors.adw.css.j2", _scheme, output_path)

        content = output_path.read_text()
        define_lines = [line for line in content.splitlines() if line.startswith("@define-color")]

        assert len(define_lines) == len(_EXPECTED_SLOTS)
        for line in define_lines:
            assert _DEFINE_COLOR_RE.fullmatch(line)

    def test_render_passthrough_block_matches_gtk_css(
        self, _bundled_templates_dir: Path, _scheme: ColorScheme, tmp_path: Path
    ) -> None:
        renderer = JinjaTemplateRenderer(_BundledDirResolver(_bundled_templates_dir))

        adw_path = tmp_path / "colors.adw.css"
        gtk_path = tmp_path / "colors.gtk.css"
        renderer.render("colors.adw.css.j2", _scheme, adw_path)
        renderer.render("colors.gtk.css.j2", _scheme, gtk_path)

        passthrough = [
            line for line in adw_path.read_text().splitlines() if _PASSTHROUGH_RE.fullmatch(line)
        ]
        gtk_passthrough = [
            line for line in gtk_path.read_text().splitlines() if _PASSTHROUGH_RE.fullmatch(line)
        ]

        assert len(passthrough) == 16
        assert passthrough == gtk_passthrough

    def test_render_all_hex_values_are_valid(
        self, _bundled_templates_dir: Path, _scheme: ColorScheme, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "colors.adw.css"
        renderer = JinjaTemplateRenderer(_BundledDirResolver(_bundled_templates_dir))
        renderer.render("colors.adw.css.j2", _scheme, output_path)

        defined = _parse_define_colors(output_path.read_text())
        assert len(defined) == len(_EXPECTED_SLOTS)
        hex_re = re.compile(r"#[0-9a-fA-F]{6}")
        for name, value in defined.items():
            # simple hex values, or every hex embedded in a color-mix(...)
            if value.startswith("color-mix("):
                assert "in srgb," in value, f"{name}={value}"
                embedded = re.findall(r"#[0-9a-fA-F]{6}", value)
                assert len(embedded) == 2, f"{name}={value}"
            else:
                assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), f"{name}={value}"

    def test_render_custom_properties_channel_matches_named_mapping(
        self, _bundled_templates_dir: Path, _scheme: ColorScheme, tmp_path: Path
    ) -> None:
        """libadwaita 1.4+ / GTK 4.16+ channel: the :root block must carry the
        same palette mapping as the named colors (gt-4-1 machine evidence:
        power-options-gtk stayed stock-light on @define-color alone)."""
        output_path = tmp_path / "colors.adw.css"
        renderer = JinjaTemplateRenderer(_BundledDirResolver(_bundled_templates_dir))
        renderer.render("colors.adw.css.j2", _scheme, output_path)

        content = output_path.read_text()
        assert ":root {" in content, "custom-properties channel missing"
        variables = dict(
            re.findall(
                r"^\s*(--window-bg-color|--window-fg-color|--popover-bg-color|--popover-fg-color|--dialog-bg-color|--dialog-fg-color|--headerbar-bg-color|--card-bg-color|--sidebar-bg-color|--accent-bg-color|--accent-color|--shade-color): (.+?);$",
                content,
                re.MULTILINE,
            )
        )

        expected: dict[str, str] = {
            "--window-bg-color": "background",
            "--window-fg-color": "foreground",
            "--popover-bg-color": "mix:colors[1]:45%",
            "--popover-fg-color": "foreground",
            "--dialog-bg-color": "background",
            "--dialog-fg-color": "foreground",
            "--headerbar-bg-color": "mix:colors[2]:55%",
            "--card-bg-color": "mix:colors[3]:35%",
            "--sidebar-bg-color": "mix:colors[1]:45%",
            "--accent-bg-color": "colors[4]",
            "--accent-color": "colors[5]",
            "--shade-color": "colors[1]",
        }
        assert set(variables) == set(expected)
        for var, slot in expected.items():
            assert variables[var] == _slot_hex(_scheme, slot), f"{var} <- {slot}"
