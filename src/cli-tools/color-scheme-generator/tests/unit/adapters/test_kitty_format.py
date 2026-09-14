from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from color_scheme_generator.adapters.jinja_template_renderer import JinjaTemplateRenderer
from color_scheme_generator.adapters.local_processor import LocalProcessor
from color_scheme_generator.domain.enums import Backend, ColorFormat
from color_scheme_generator.domain.models import (
    Color,
    ColorScheme,
    GenerationRequest,
    GeneratorConfig,
)

# Pinned, deterministic rendering of the fixture scheme below. Hard-coded on
# purpose: any drift in the template (extra keys, metadata, wrong syntax) fails
# loudly rather than being recomputed from the same code under test.
_EXPECTED_FRAGMENT = "\n".join(
    [
        "background #1a1b26",
        "foreground #c0caf5",
        "cursor #f7768e",
        "color0 #000000",
        "color1 #111111",
        "color2 #222222",
        "color3 #333333",
        "color4 #444444",
        "color5 #555555",
        "color6 #666666",
        "color7 #777777",
        "color8 #888888",
        "color9 #999999",
        "color10 #aaaaaa",
        "color11 #bbbbbb",
        "color12 #cccccc",
        "color13 #dddddd",
        "color14 #eeeeee",
        "color15 #ffffff",
        "selection_background #1a1b26",
        "selection_foreground #c0caf5",
    ]
)

_EXPECTED_KEYS = [
    "background",
    "foreground",
    "cursor",
    *(f"color{i}" for i in range(16)),
    "selection_background",
    "selection_foreground",
]

_PLAIN_LINE_RE = re.compile(r"^(?P<key>[a-z0-9_]+) #[0-9a-f]{6}$")


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


class TestKittyFormat:
    def test_render_exact_fragment(
        self, _bundled_templates_dir: Path, _scheme: ColorScheme, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "colors.kitty"
        renderer = JinjaTemplateRenderer(_BundledDirResolver(_bundled_templates_dir))
        renderer.render("colors.kitty.j2", _scheme, output_path)

        assert output_path.read_text() == _EXPECTED_FRAGMENT

    def test_render_matches_plain_kitty_syntax_contract(
        self, _bundled_templates_dir: Path, _scheme: ColorScheme, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "colors.kitty"
        renderer = JinjaTemplateRenderer(_BundledDirResolver(_bundled_templates_dir))
        renderer.render("colors.kitty.j2", _scheme, output_path)

        content = output_path.read_text()
        lines = content.splitlines()

        assert len(lines) == 21
        assert [line.split(" ")[0] for line in lines] == _EXPECTED_KEYS
        for line in lines:
            assert _PLAIN_LINE_RE.fullmatch(line), line

    def test_render_has_no_variable_rgb_or_metadata(
        self, _bundled_templates_dir: Path, _scheme: ColorScheme, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "colors.kitty"
        renderer = JinjaTemplateRenderer(_BundledDirResolver(_bundled_templates_dir))
        renderer.render("colors.kitty.j2", _scheme, output_path)

        content = output_path.read_text()
        assert "$" not in content
        assert "rgb(" not in content
        assert "# generated" not in content
        assert "source-image" not in content
        assert "generated-at" not in content

    def test_selection_colors_are_palette_derived(
        self, _bundled_templates_dir: Path, _scheme: ColorScheme, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "colors.kitty"
        renderer = JinjaTemplateRenderer(_BundledDirResolver(_bundled_templates_dir))
        renderer.render("colors.kitty.j2", _scheme, output_path)

        content = output_path.read_text()
        assert f"selection_background {_scheme.background.hex}" in content
        assert f"selection_foreground {_scheme.foreground.hex}" in content

    def test_local_processor_writes_colors_kitty(
        self, _bundled_templates_dir: Path, _scheme: ColorScheme, tmp_path: Path
    ) -> None:
        from unittest.mock import MagicMock

        mock_gen = MagicMock()
        mock_gen.is_available.return_value = True
        mock_gen.generate.return_value = _scheme

        renderer = JinjaTemplateRenderer(_BundledDirResolver(_bundled_templates_dir))
        processor = LocalProcessor({Backend.CUSTOM: mock_gen}, template_renderer=renderer)

        request = GenerationRequest(
            image_path=Path("/tmp/wallpaper.png"),
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.KITTY,),
                output_dir=tmp_path,
            ),
        )

        result = processor.process_generate(request, object())

        output_path = tmp_path / "colors.kitty"
        assert result.success is True
        assert output_path in result.output_files
        assert output_path.read_text() == _EXPECTED_FRAGMENT


@pytest.mark.skipif(shutil.which("kitty") is None, reason="kitty binary not available")
class TestKittyParsesFragment:
    def test_kitty_parses_fragment_cleanly(
        self, _bundled_templates_dir: Path, _scheme: ColorScheme, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "colors.kitty"
        renderer = JinjaTemplateRenderer(_BundledDirResolver(_bundled_templates_dir))
        renderer.render("colors.kitty.j2", _scheme, output_path)

        script = (
            "from kitty.config import load_config\n"
            f"opts = load_config({str(output_path)!r})\n"
            "assert tuple(opts.background) == (26, 27, 38), opts.background\n"
            "assert tuple(opts.foreground) == (192, 202, 245), opts.foreground\n"
            "assert tuple(opts.color0) == (0, 0, 0), opts.color0\n"
            "assert tuple(opts.color15) == (255, 255, 255), opts.color15\n"
        )
        proc = subprocess.run(
            ["kitty", "+runpy", script],
            capture_output=True,
            text=True,
            check=False,
        )

        combined = proc.stdout + proc.stderr
        assert "Ignoring invalid config line" not in combined, combined
        assert proc.returncode == 0, combined
