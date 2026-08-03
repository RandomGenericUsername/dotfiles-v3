from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


class TestRenderIntegration:
    def test_render_all_icons(
        self, cli_deps_integration, integration_env, integration_icons_yaml, tmp_path
    ):
        result = CliRunner().invoke(app, ["render", str(integration_icons_yaml)])
        assert result.exit_code == 0, result.stderr
        base = integration_icons_yaml.parent
        assert (base / "out" / "battery" / "battery-0.svg").exists()
        assert (base / "out" / "battery" / "battery-100.svg").exists()
        assert (base / "out" / "network" / "wifi.svg").exists()

    def test_render_output_summary(
        self, cli_deps_integration, integration_env, integration_icons_yaml
    ):
        result = CliRunner().invoke(app, ["render", str(integration_icons_yaml)])
        assert "Rendered:" in result.stdout
        assert "3 icon(s) rendered." in result.stdout

    def test_placeholders_resolved(
        self, cli_deps_integration, integration_env, integration_icons_yaml
    ):
        CliRunner().invoke(app, ["render", str(integration_icons_yaml)])
        base = integration_icons_yaml.parent
        battery0 = (base / "out" / "battery" / "battery-0.svg").read_text()
        assert "#1a1a2e" in battery0
        assert "{{" not in battery0

    def test_render_single_icon_group(
        self, cli_deps_integration, integration_env, integration_icons_yaml
    ):
        result = CliRunner().invoke(
            app, ["render", str(integration_icons_yaml), "--icon", "battery"]
        )
        assert result.exit_code == 0, result.stderr
        base = integration_icons_yaml.parent
        assert (base / "out" / "battery" / "battery-0.svg").exists()
        assert not (base / "out" / "network" / "wifi.svg").exists()

    def test_render_unknown_icon_exits_nonzero(
        self, cli_deps_integration, integration_env, integration_icons_yaml
    ):
        result = CliRunner().invoke(
            app, ["render", str(integration_icons_yaml), "--icon", "nonexistent"]
        )
        assert result.exit_code == 1
        assert "Icon 'nonexistent' not found" in result.stderr

    def test_render_no_flags_uses_settings(self, cli_deps_integration, tmp_path, monkeypatch):
        """settings.toml (not env) drives the roots."""
        colors = tmp_path / "colors.yaml"
        colors.write_text('special:\n  background: "#112233"\ncolors: []\n')
        tpl = tmp_path / "tpls"
        (tpl / "battery").mkdir(parents=True)
        (tpl / "battery" / "battery-0.svg").write_text('<svg><path fill="{{background}}"/></svg>')
        settings = tmp_path / "settings.toml"
        settings.write_text(
            "[output]\n"
            'output_dir = "/tmp/itr-settings-out"\n'
            "verbosity = 1\n"
            "[templates]\n"
            f'dir = "{tpl}"\n'
            "[color_scheme]\n"
            f'path = "{colors}"\n'
        )
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
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(app, ["render", str(icons), "--config", str(settings)])
        assert result.exit_code == 0, result.stderr
        rendered = Path("/tmp/itr-settings-out") / "battery" / "battery-0.svg"
        assert rendered.exists()
        assert "#112233" in rendered.read_text()

    def test_missing_required_root_fails_fast(self, cli_deps_integration, tmp_path):
        icons = tmp_path / "icons.yaml"
        icons.write_text("battery:\n  variants: []\n")
        result = CliRunner().invoke(app, ["render", str(icons)])
        assert result.exit_code == 1
        assert "templates_dir" in result.stderr
        assert "--template-dir" in result.stderr
        assert "ICON_RENDERER__TEMPLATES__DIR" in result.stderr
