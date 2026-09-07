from __future__ import annotations

import json

from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


def _manifest() -> str:
    return (
        "# icons manifest — comments are load-bearing\n"
        "battery:\n"
        "  # group mappings\n"
        "  color_mappings:\n"
        '    COLOR_ACCENT: "color12"\n'
        "  variants:\n"
        "    - name: battery-0\n"
        "      template: battery-0.svg\n"
        "      output: battery-0.svg\n"
    )


def _write_scheme(tmp_path) -> None:
    colors = [
        "#1a1a2e",  # color0
        "#e94560",  # color1
        "#0f3460",  # color2
        "#3f6ea8",  # color3
        "#16213e",  # color4
        "#533483",  # color5
        "#0f3460",  # color6
        "#e0e0e0",  # color7
        "#4b525d",  # color8
        "#b8bfc9",  # color9
        "#95d698",  # color10
        "#e6c882",  # color11
        "#6ea8fe",  # color12
    ]
    (tmp_path / "colors.yaml").write_text(
        "special:\n"
        '  background: "#1a1a2e"\n'
        '  foreground: "#e0e0e0"\n'
        "colors:\n" + "".join(f'  - "{color}"\n' for color in colors)
    )


class TestMappingSetIntegration:
    def test_group_set_preserves_comments(self, cli_deps_integration, integration_env, tmp_path):
        _write_scheme(tmp_path)
        (tmp_path / "battery-0.svg").write_text("<svg/>")
        icons = tmp_path / "icons.yaml"
        icons.write_text(_manifest())
        result = CliRunner().invoke(
            app,
            [
                "mapping",
                "set",
                str(icons),
                "--icon",
                "battery",
                "--placeholder",
                "COLOR_ACCENT",
                "--token",
                "color10",
            ],
        )
        assert result.exit_code == 0, result.stderr
        text = icons.read_text()
        assert "# icons manifest" in text
        assert "# group mappings" in text
        assert '"color10"' in text

    def test_variant_override_then_show_reports_variant_origin(
        self, cli_deps_integration, integration_env, tmp_path
    ):
        _write_scheme(tmp_path)
        (tmp_path / "battery-0.svg").write_text("<svg/>")
        icons = tmp_path / "icons.yaml"
        icons.write_text(_manifest())
        result = CliRunner().invoke(
            app,
            [
                "mapping",
                "set",
                str(icons),
                "--icon",
                "battery",
                "--variant",
                "battery-0",
                "--placeholder",
                "COLOR_ACCENT",
                "--token",
                "color3",
            ],
        )
        assert result.exit_code == 0, result.stderr
        shown = CliRunner().invoke(
            app,
            [
                "--output-format",
                "json",
                "mapping",
                "show",
                str(icons),
                "--icon",
                "battery",
            ],
        )
        assert shown.exit_code == 0, shown.stderr
        entries = {
            mapping["placeholder"]: mapping
            for mapping in json.loads(shown.stdout)["groups"][0]["variants"][0]["mappings"]
        }
        assert entries["COLOR_ACCENT"] == {
            "placeholder": "COLOR_ACCENT",
            "token": "color3",
            "origin": "variant",
        }

    def test_dry_run_diff_leaves_file_identical(
        self, cli_deps_integration, integration_env, tmp_path
    ):
        _write_scheme(tmp_path)
        (tmp_path / "battery-0.svg").write_text("<svg/>")
        icons = tmp_path / "icons.yaml"
        icons.write_text(_manifest())
        before = icons.read_bytes()
        result = CliRunner().invoke(
            app,
            [
                "mapping",
                "set",
                str(icons),
                "--icon",
                "battery",
                "--placeholder",
                "COLOR_ACCENT",
                "--token",
                "color10",
                "--dry-run",
                "--diff",
            ],
        )
        assert result.exit_code == 0, result.stderr
        assert icons.read_bytes() == before
        assert '-    COLOR_ACCENT: "color12"' in result.stdout
        assert '+    COLOR_ACCENT: "color10"' in result.stdout

    def test_unknown_token_rejected_without_write(
        self, cli_deps_integration, integration_env, tmp_path
    ):
        _write_scheme(tmp_path)
        (tmp_path / "battery-0.svg").write_text("<svg/>")
        icons = tmp_path / "icons.yaml"
        icons.write_text(_manifest())
        before = icons.read_bytes()
        result = CliRunner().invoke(
            app,
            [
                "mapping",
                "set",
                str(icons),
                "--icon",
                "battery",
                "--placeholder",
                "COLOR_ACCENT",
                "--token",
                "surface",
            ],
        )
        assert result.exit_code == 1
        assert icons.read_bytes() == before

    def test_unknown_group_rejected_without_write(
        self, cli_deps_integration, integration_env, tmp_path
    ):
        _write_scheme(tmp_path)
        icons = tmp_path / "icons.yaml"
        icons.write_text(_manifest())
        before = icons.read_bytes()
        result = CliRunner().invoke(
            app,
            [
                "mapping",
                "set",
                str(icons),
                "--icon",
                "nope",
                "--placeholder",
                "K",
                "--token",
                "color10",
            ],
        )
        assert result.exit_code == 1
        assert icons.read_bytes() == before


class TestMappingSetDefaultIntegration:
    def _defaults(self, tmp_path) -> object:
        path = tmp_path / "defaults.yaml"
        path.write_text("defaults:\n  COLOR_ACCENT: accent-muted\n  COLOR_FOREGROUND: foreground\n")
        return path

    def test_set_default_reports_shadows(self, cli_deps_integration, integration_env, tmp_path):
        _write_scheme(tmp_path)
        defaults = self._defaults(tmp_path)
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
            "  template_dir: ./\n"
            "  output_dir: out/\n"
            "  color_mappings:\n"
            "    COLOR_ACCENT: color12\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n"
        )
        (tmp_path / "battery-0.svg").write_text("<svg/>")
        result = CliRunner().invoke(
            app,
            [
                "mapping",
                "set-default",
                str(defaults),
                "--placeholder",
                "COLOR_ACCENT",
                "--token",
                "color3",
                "--icons",
                str(icons),
            ],
        )
        assert result.exit_code == 0, result.stderr
        assert "Set defaults.COLOR_ACCENT = color3." in result.stdout
        assert "Shadowing groups: battery" in result.stdout
        assert "COLOR_ACCENT: color3" in defaults.read_text()

    def test_set_default_json_shadows(self, cli_deps_integration, integration_env, tmp_path):
        _write_scheme(tmp_path)
        defaults = self._defaults(tmp_path)
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
            "  color_mappings:\n"
            "    COLOR_ACCENT: color12\n"
            "  variants:\n"
            "    - name: battery-0\n"
            "      template: battery-0.svg\n"
            "      output: battery-0.svg\n"
        )
        result = CliRunner().invoke(
            app,
            [
                "--output-format",
                "json",
                "mapping",
                "set-default",
                str(defaults),
                "--placeholder",
                "COLOR_ACCENT",
                "--token",
                "color3",
                "--icons",
                str(icons),
            ],
        )
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["shadows"] == ["battery"]

    def test_set_default_unknown_placeholder_rejected_without_write(
        self, cli_deps_integration, integration_env, tmp_path
    ):
        _write_scheme(tmp_path)
        defaults = self._defaults(tmp_path)
        before = defaults.read_bytes()
        result = CliRunner().invoke(
            app,
            [
                "mapping",
                "set-default",
                str(defaults),
                "--placeholder",
                "NOPE",
                "--token",
                "color3",
            ],
        )
        assert result.exit_code == 1
        assert defaults.read_bytes() == before
