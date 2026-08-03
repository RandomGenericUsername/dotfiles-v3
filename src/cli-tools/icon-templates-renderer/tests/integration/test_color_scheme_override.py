from __future__ import annotations

from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


class TestColorSchemeOverride:
    def test_cli_color_scheme_override(self, cli_deps_integration, integration_env, tmp_path):
        alt = tmp_path / "colors-alt.yaml"
        alt.write_text('special:\n  background: "#aabbcc"\ncolors: []\n')
        battery_dir = tmp_path / "battery"
        battery_dir.mkdir(parents=True)
        (battery_dir / "battery-0.svg").write_text('<svg><path fill="{{background}}"/></svg>')
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
            "  template_dir: battery/\n"
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

    def test_global_scheme_applies_to_all_groups(
        self, cli_deps_integration, integration_env, tmp_path
    ):
        alt = tmp_path / "colors-alt.yaml"
        alt.write_text('special:\n  background: "#aabbcc"\n  foreground: "#ddeeff"\ncolors: []\n')
        battery_dir = tmp_path / "battery"
        battery_dir.mkdir(parents=True)
        (battery_dir / "battery-0.svg").write_text(
            '<svg><path fill="{{background}}" stroke="{{foreground}}"/></svg>'
        )
        network_dir = tmp_path / "network"
        network_dir.mkdir(parents=True)
        (network_dir / "wifi.svg").write_text(
            '<svg><path fill="{{background}}" stroke="{{foreground}}"/></svg>'
        )
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
            "  template_dir: battery/\n"
            "  output_dir: out/battery/\n"
            "  color_mappings:\n"
            "    background: background\n"
            "    foreground: foreground\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n"
            "network:\n"
            "  template_dir: network/\n"
            "  output_dir: out/network/\n"
            "  color_mappings:\n"
            "    background: background\n"
            "    foreground: foreground\n"
            "  variants:\n"
            "    - name: wifi\n"
            "      template: wifi.svg\n"
            "      output: wifi.svg\n"
        )
        # integration_env already sets COLOR_SCHEME__PATH to tmp_path/colors.yaml.
        # Create it so the global scheme is that file.
        (tmp_path / "colors.yaml").write_text(alt.read_text())
        result = CliRunner().invoke(app, ["render", str(icons)])
        assert result.exit_code == 0, result.stderr
        battery_out = tmp_path / "out" / "battery" / "battery-0.svg"
        network_out = tmp_path / "out" / "network" / "wifi.svg"
        assert "#aabbcc" in battery_out.read_text()
        assert "#aabbcc" in network_out.read_text()
        assert "{{" not in battery_out.read_text()
