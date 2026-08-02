from __future__ import annotations

from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


class TestColorSchemeOverride:
    def test_top_level_color_scheme_used_for_all_groups(self, cli_deps_integration, tmp_path):
        alt = tmp_path / "colors-alt.yaml"
        alt.write_text('special:\n  background: "#aabbcc"\n  foreground: "#ddeeff"\ncolors: []\n')
        template_dir = tmp_path / "templates" / "battery"
        template_dir.mkdir(parents=True)
        (template_dir / "battery-0.svg").write_text(
            '<svg><path fill="{{background}}" stroke="{{foreground}}"/></svg>'
        )
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            f"color_scheme: {alt}\n"
            "battery:\n"
            "  color_scheme: /nonexistent/ignored.yaml\n"
            "  template_dir: templates/battery/\n"
            "  output_dir: out/global-colors/\n"
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
        out = tmp_path / "out" / "global-colors" / "battery-0.svg"
        assert out.exists()
        rendered = out.read_text()
        assert "#aabbcc" in rendered
        assert "{{" not in rendered

    def test_cli_color_scheme_override(self, cli_deps_integration, tmp_path):
        alt = tmp_path / "colors-alt.yaml"
        alt.write_text('special:\n  background: "#aabbcc"\ncolors: []\n')
        template_dir = tmp_path / "templates" / "battery"
        template_dir.mkdir(parents=True)
        (template_dir / "battery-0.svg").write_text('<svg><path fill="{{background}}"/></svg>')
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
            "  color_scheme: /nonexistent/ignored.yaml\n"
            "  template_dir: templates/battery/\n"
            "  output_dir: out/cli-colors/\n"
            "  color_mappings:\n"
            "    background: background\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n"
        )
        result = CliRunner().invoke(app, ["render", str(icons), "--color-scheme", str(alt)])
        assert result.exit_code == 0, result.stderr
        out = tmp_path / "out" / "cli-colors" / "battery-0.svg"
        assert "#aabbcc" in out.read_text()
