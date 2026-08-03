from __future__ import annotations

from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


class TestListIntegration:
    def test_list_shows_all_groups(
        self, cli_deps_integration, integration_env, integration_icons_yaml
    ):
        result = CliRunner().invoke(app, ["list", str(integration_icons_yaml)])
        assert result.exit_code == 0, result.stderr
        assert "battery:" in result.stdout
        assert "network:" in result.stdout

    def test_list_icon_shows_only_that_group(
        self, cli_deps_integration, integration_env, integration_icons_yaml
    ):
        result = CliRunner().invoke(app, ["list", str(integration_icons_yaml), "--icon", "battery"])
        assert result.exit_code == 0, result.stderr
        assert "Variants:" in result.stdout
        assert "network:" not in result.stdout

    def test_list_unknown_icon_exits_nonzero(
        self, cli_deps_integration, integration_env, integration_icons_yaml
    ):
        result = CliRunner().invoke(
            app, ["list", str(integration_icons_yaml), "--icon", "nonexistent"]
        )
        assert result.exit_code == 1

    def test_list_succeeds_with_no_roots_configured(self, cli_deps_integration, tmp_path):
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n"
            "network:\n"
            "  variants:\n"
            "    - name: wifi\n"
            "      template: wifi.svg\n"
            "      output: wifi.svg\n"
        )
        result = CliRunner().invoke(app, ["list", str(icons)])
        assert result.exit_code == 0, result.stderr
        assert "battery:" in result.stdout
        assert "network:" in result.stdout
