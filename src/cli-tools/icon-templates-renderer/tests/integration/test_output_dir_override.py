from __future__ import annotations

from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


class TestOutputDirOverride:
    def test_env_output_dir_drives_output_location(
        self, cli_deps_integration, integration_env, tmp_path
    ):
        colors = tmp_path / "colors.yaml"
        colors.write_text("special:\n  background: '#000000'\ncolors: []\n")
        battery_dir = tmp_path / "battery"
        battery_dir.mkdir(parents=True)
        (battery_dir / "battery-0.svg").write_text('<svg><path fill="{{background}}"/></svg>')
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
            "  template_dir: battery/\n"
            "  output_dir: battery/\n"
            "  color_mappings:\n"
            "    background: background\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n"
        )
        result = CliRunner().invoke(app, ["render", str(icons)])
        assert result.exit_code == 0, result.stderr
        assert (tmp_path / "battery" / "battery-0.svg").exists()

    def test_cli_output_dir_override(self, cli_deps_integration, integration_env, tmp_path):
        colors = tmp_path / "colors.yaml"
        colors.write_text("special:\n  background: '#000000'\ncolors: []\n")
        battery_dir = tmp_path / "battery"
        battery_dir.mkdir(parents=True)
        (battery_dir / "battery-0.svg").write_text('<svg><path fill="{{background}}"/></svg>')
        override_out = tmp_path / "cli-out"
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
            "  template_dir: battery/\n"
            "  output_dir: battery/\n"
            "  color_mappings:\n"
            "    background: background\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n"
        )
        result = CliRunner().invoke(app, ["render", str(icons), "--output-dir", str(override_out)])
        assert result.exit_code == 0, result.stderr
        assert (override_out / "battery" / "battery-0.svg").exists()
