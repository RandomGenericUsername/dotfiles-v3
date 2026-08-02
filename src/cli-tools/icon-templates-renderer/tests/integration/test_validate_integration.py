from __future__ import annotations

from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


class TestValidateIntegration:
    def test_validate_valid_config_passes(self, cli_deps_integration, integration_icons_yaml):
        result = CliRunner().invoke(app, ["validate", str(integration_icons_yaml)])
        assert result.exit_code == 0, result.stderr
        assert "Validation passed." in result.stdout

    def test_validate_missing_file_exits_nonzero(self, cli_deps_integration, tmp_path):
        result = CliRunner().invoke(app, ["validate", str(tmp_path / "nope.yaml")])
        assert result.exit_code == 1
        assert "Error: YAML file not found" in result.stderr

    def test_validate_missing_template_fails(self, cli_deps_integration, tmp_path):
        colors = tmp_path / "colors.yaml"
        colors.write_text("special:\n  background: '#000000'\ncolors: []\n")
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
            f"  color_scheme: {colors}\n"
            "  template_dir: nonexistent/\n"
            "  output_dir: out/\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n"
        )
        result = CliRunner().invoke(app, ["validate", str(icons)])
        assert result.exit_code == 1
        assert "Error:" in result.stderr

    def test_validate_missing_color_scheme_fails(self, cli_deps_integration, tmp_path):
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
            "  color_scheme: missing.yaml\n"
            "  template_dir: templates/\n"
            "  output_dir: out/\n"
            "  variants: []\n"
        )
        result = CliRunner().invoke(app, ["validate", str(icons)])
        assert result.exit_code == 1
        assert "Color scheme not found:" in result.stderr
