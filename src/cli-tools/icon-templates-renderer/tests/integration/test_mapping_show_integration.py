from __future__ import annotations

import json

from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


def _show_json(*args: str) -> dict:
    result = CliRunner().invoke(app, ["--output-format", "json", "mapping", "show", *args])
    assert result.exit_code == 0, result.stderr
    return json.loads(result.stdout)


class TestMappingShowIntegration:
    def test_origins_attributed(
        self, cli_deps_integration, integration_env, integration_icons_yaml
    ):
        payload = _show_json(str(integration_icons_yaml))
        groups = {group["group"]: group for group in payload["groups"]}
        battery = {variant["variant"]: variant for variant in groups["battery"]["variants"]}
        entries = {mapping["placeholder"]: mapping for mapping in battery["battery-0"]["mappings"]}
        assert entries["background"] == {
            "placeholder": "background",
            "token": "background",
            "origin": "group",
        }
        assert entries["foreground"]["origin"] == "group"

    def test_icon_filter(self, cli_deps_integration, integration_env, integration_icons_yaml):
        payload = _show_json(str(integration_icons_yaml), "--icon", "network")
        assert [group["group"] for group in payload["groups"]] == ["network"]

    def test_template_bodies_present(
        self, cli_deps_integration, integration_env, integration_icons_yaml
    ):
        payload = _show_json(str(integration_icons_yaml))
        bodies = [
            variant["svg_body"] for group in payload["groups"] for variant in group["variants"]
        ]
        assert bodies
        assert all("{{" in body for body in bodies)

    def test_palette_table_present(
        self, cli_deps_integration, integration_env, integration_icons_yaml
    ):
        payload = _show_json(str(integration_icons_yaml))
        assert payload["palette"]["background"] == "#1a1a2e"
        assert payload["palette"]["color1"] == "#e94560"

    def test_missing_tokens_listed_with_exit_zero(
        self, cli_deps_integration, integration_env, tmp_path
    ):
        (tmp_path / "colors.yaml").write_text(
            'special:\n  background: "#1a1a2e"\ncolors:\n  - "#1a1a2e"\n'
        )
        (tmp_path / "ghost.svg").write_text('<svg><path fill="{{ghost}}"/></svg>')
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "spooky:\n"
            "  template_dir: ./\n"
            "  output_dir: out/\n"
            "  color_mappings:\n"
            "    ghost: surface\n"
            "    solid: '#ff0066'\n"
            "  variants:\n"
            "    - name: apparition\n"
            "      template: ghost.svg\n"
            "      output: ghost.svg\n"
        )
        payload = _show_json(str(icons))
        assert payload["missing_tokens"] == ["surface"]
        assert payload["shadows"] == {"ghost": ["spooky"], "solid": ["spooky"]}

    def test_plain_output(self, cli_deps_integration, integration_env, integration_icons_yaml):
        result = CliRunner().invoke(app, ["mapping", "show", str(integration_icons_yaml)])
        assert result.exit_code == 0, result.stderr
        assert "battery:" in result.stdout
        assert "background: background [group]" in result.stdout

    def test_unknown_icon_exits_nonzero(
        self, cli_deps_integration, integration_env, integration_icons_yaml
    ):
        result = CliRunner().invoke(
            app, ["mapping", "show", str(integration_icons_yaml), "--icon", "nonexistent"]
        )
        assert result.exit_code == 1
