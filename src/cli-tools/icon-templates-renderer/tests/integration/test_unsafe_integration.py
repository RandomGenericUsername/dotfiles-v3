from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


@pytest.fixture
def broken_icons(tmp_path: Path) -> Path:
    """A config whose template contains an unresolved placeholder."""
    colors = tmp_path / "colors.yaml"
    colors.write_text("special:\n  background: '#000000'\ncolors: []\n")
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "icon.svg").write_text('<svg><path fill="{{unknown_color}}"/></svg>')
    icons = tmp_path / "icons.yaml"
    icons.write_text(
        "broken:\n"
        "  template_dir: templates/\n"
        "  output_dir: out/broken/\n"
        "  variants:\n"
        "    - name: icon\n"
        "      template: icon.svg\n"
        "      output: icon.svg\n"
    )
    return icons


class TestUnsafeModeIntegration:
    def test_unresolved_fails_by_default(self, cli_deps_integration, integration_env, broken_icons):
        result = CliRunner().invoke(app, ["render", str(broken_icons)])
        assert result.exit_code == 1
        assert "no entry in color_mappings" in result.stderr

    def test_unsafe_flag_succeeds(self, cli_deps_integration, integration_env, broken_icons):
        result = CliRunner().invoke(app, ["render", str(broken_icons), "--unsafe"])
        assert result.exit_code == 0, result.stderr
        out = broken_icons.parent / "out" / "broken" / "icon.svg"
        assert out.exists()
        assert "{{unknown_color}}" in out.read_text()

    def test_unsafe_true_in_yaml_succeeds(self, cli_deps_integration, integration_env, tmp_path):
        colors = tmp_path / "colors.yaml"
        colors.write_text("special:\n  background: '#000000'\ncolors: []\n")
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "icon.svg").write_text('<svg><path fill="{{unknown_color}}"/></svg>')
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "broken:\n"
            "  template_dir: templates/\n"
            "  output_dir: out/broken-yaml/\n"
            "  unsafe: true\n"
            "  variants:\n"
            "    - name: icon\n"
            "      template: icon.svg\n"
            "      output: icon.svg\n"
        )
        result = CliRunner().invoke(app, ["render", str(icons)])
        assert result.exit_code == 0, result.stderr

    def test_unsafe_placeholder_preserved(self, cli_deps_integration, integration_env, tmp_path):
        colors = tmp_path / "colors.yaml"
        colors.write_text("special:\n  background: '#000000'\ncolors: []\n")
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "icon.svg").write_text('<svg><path fill="{{unknown_color}}"/></svg>')
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "broken:\n"
            "  template_dir: templates/\n"
            "  output_dir: out/broken-yaml/\n"
            "  unsafe: true\n"
            "  variants:\n"
            "    - name: icon\n"
            "      template: icon.svg\n"
            "      output: icon.svg\n"
        )
        CliRunner().invoke(app, ["render", str(icons)])
        out = tmp_path / "out" / "broken-yaml" / "icon.svg"
        assert "{{unknown_color}}" in out.read_text()
