from __future__ import annotations

from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


class TestRenderIntegration:
    def test_render_all_icons(self, cli_deps_integration, integration_icons_yaml, tmp_path):
        result = CliRunner().invoke(app, ["render", str(integration_icons_yaml)])
        assert result.exit_code == 0, result.stderr
        base = integration_icons_yaml.parent
        assert (base / "out" / "battery" / "battery-0.svg").exists()
        assert (base / "out" / "battery" / "battery-100.svg").exists()
        assert (base / "out" / "network" / "wifi.svg").exists()

    def test_render_output_summary(self, cli_deps_integration, integration_icons_yaml):
        result = CliRunner().invoke(app, ["render", str(integration_icons_yaml)])
        assert "Rendered:" in result.stdout
        assert "3 icon(s) rendered." in result.stdout

    def test_placeholders_resolved(self, cli_deps_integration, integration_icons_yaml):
        CliRunner().invoke(app, ["render", str(integration_icons_yaml)])
        base = integration_icons_yaml.parent
        battery0 = (base / "out" / "battery" / "battery-0.svg").read_text()
        assert "#1a1a2e" in battery0
        assert "{{" not in battery0

    def test_render_single_icon_group(self, cli_deps_integration, integration_icons_yaml):
        result = CliRunner().invoke(
            app, ["render", str(integration_icons_yaml), "--icon", "battery"]
        )
        assert result.exit_code == 0, result.stderr
        base = integration_icons_yaml.parent
        assert (base / "out" / "battery" / "battery-0.svg").exists()
        assert not (base / "out" / "network" / "wifi.svg").exists()

    def test_render_unknown_icon_exits_nonzero(self, cli_deps_integration, integration_icons_yaml):
        result = CliRunner().invoke(
            app, ["render", str(integration_icons_yaml), "--icon", "nonexistent"]
        )
        assert result.exit_code == 1
        assert "Icon 'nonexistent' not found" in result.stderr
