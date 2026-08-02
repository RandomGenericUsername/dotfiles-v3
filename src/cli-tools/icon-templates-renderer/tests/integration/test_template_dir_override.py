from __future__ import annotations

from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


class TestTemplateDirOverride:
    def test_relative_template_dir_resolves_from_yaml_location(
        self, cli_deps_integration, tmp_path
    ):
        colors = tmp_path / "colors.yaml"
        colors.write_text(
            'special:\n  background: "#1a1a2e"\n  foreground: "#e0e0e0"\ncolors: []\n'
        )
        template_dir = tmp_path / "templates" / "battery"
        template_dir.mkdir(parents=True)
        (template_dir / "battery-0.svg").write_text(
            '<svg><path fill="{{background}}" stroke="{{foreground}}"/></svg>'
        )
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
            f"  color_scheme: {colors}\n"
            "  template_dir: templates/battery/\n"
            "  output_dir: out/relative/\n"
            "  color_mappings:\n"
            "    background: background\n"
            "    foreground: foreground\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n"
        )
        result = CliRunner().invoke(app, ["render", str(icons)])
        assert result.exit_code == 0, result.stderr
        out = tmp_path / "out" / "relative" / "battery-0.svg"
        assert out.exists()
        assert "#1a1a2e" in out.read_text()

    def test_cli_template_dir_override(self, cli_deps_integration, tmp_path):
        colors = tmp_path / "colors.yaml"
        colors.write_text("special:\n  background: '#000000'\ncolors: []\n")
        override_templates = tmp_path / "alt-templates" / "battery"
        override_templates.mkdir(parents=True)
        (override_templates / "battery-0.svg").write_text(
            '<svg><path fill="{{background}}"/></svg>'
        )
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
            f"  color_scheme: {colors}\n"
            "  template_dir: battery/\n"
            "  output_dir: out/override/\n"
            "  color_mappings:\n"
            "    background: background\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n"
        )
        result = CliRunner().invoke(
            app,
            ["render", str(icons), "--template-dir", str(tmp_path / "alt-templates")],
        )
        assert result.exit_code == 0, result.stderr
        out = tmp_path / "out" / "override" / "battery-0.svg"
        assert out.exists()

    def test_top_level_templates_root(self, cli_deps_integration, tmp_path):
        colors = tmp_path / "colors.yaml"
        colors.write_text("special:\n  background: '#000000'\ncolors: []\n")
        root = tmp_path / "tpls"
        battery_dir = root / "battery"
        battery_dir.mkdir(parents=True)
        (battery_dir / "battery-0.svg").write_text('<svg><path fill="{{background}}"/></svg>')
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            f"templates_root: {root}\n"
            "battery:\n"
            f"  color_scheme: {colors}\n"
            "  template_dir: battery/\n"
            "  output_dir: out/rooted/\n"
            "  color_mappings:\n"
            "    background: background\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n"
        )
        result = CliRunner().invoke(app, ["render", str(icons)])
        assert result.exit_code == 0, result.stderr
        assert (tmp_path / "out" / "rooted" / "battery-0.svg").exists()
