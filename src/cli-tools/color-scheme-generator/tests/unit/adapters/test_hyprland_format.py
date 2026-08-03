from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from color_scheme_generator.adapters.jinja_template_renderer import JinjaTemplateRenderer
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.models import Color, ColorScheme


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


class TestHyprlandFormat:
    def test_render_matches_hyprland_syntax_contract(
        self, _bundled_templates_dir: Path, _scheme: ColorScheme, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "colors.conf"
        renderer = JinjaTemplateRenderer(_BundledDirResolver(_bundled_templates_dir))
        renderer.render("colors.conf.j2", _scheme, output_path)

        content = output_path.read_text()

        lines = content.strip().splitlines()
        assert len(lines) == 20

        expected_order = ["$background", "$foreground", "$cursor", "$accent"]
        expected_order += [f"$color{i}" for i in range(16)]
        assert [line.split(" = ")[0] for line in lines] == expected_order

        for line in lines:
            assert re.fullmatch(r"\$[a-z0-9]+ = rgb\([0-9a-f]{6}\)", line)

    def test_render_strips_hash_and_uses_color1_for_accent(
        self, _bundled_templates_dir: Path, _scheme: ColorScheme, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "colors.conf"
        renderer = JinjaTemplateRenderer(_BundledDirResolver(_bundled_templates_dir))
        renderer.render("colors.conf.j2", _scheme, output_path)

        content = output_path.read_text()

        assert f"$background = rgb({_scheme.background.hex[1:]})" in content
        assert f"$foreground = rgb({_scheme.foreground.hex[1:]})" in content
        assert f"$cursor = rgb({_scheme.cursor.hex[1:]})" in content
        assert f"$accent = rgb({_scheme.colors[1].hex[1:]})" in content

        assert "#" not in content
        assert ";" not in content
        assert '"' not in content
        assert "'" not in content
