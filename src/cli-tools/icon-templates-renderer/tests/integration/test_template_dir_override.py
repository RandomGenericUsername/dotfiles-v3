from __future__ import annotations

from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


class TestTemplateDirOverride:
    def test_env_templates_dir_drives_root(self, cli_deps_integration, integration_env, tmp_path):
        # integration_env points TEMPLATES__DIR at tmp_path; relative subdirs join under it.
        colors = tmp_path / "colors.yaml"
        colors.write_text(
            'special:\n  background: "#1a1a2e"\n  foreground: "#e0e0e0"\ncolors: []\n'
        )
        template_dir = tmp_path / "battery"
        template_dir.mkdir(parents=True)
        (template_dir / "battery-0.svg").write_text(
            '<svg><path fill="{{background}}" stroke="{{foreground}}"/></svg>'
        )
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
            "  template_dir: battery/\n"
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

    def test_cli_template_dir_override_wins_over_env(
        self, cli_deps_integration, integration_env, tmp_path
    ):
        # integration_env points TEMPLATES__DIR at tmp_path (a path without the real template),
        # but the CLI flag points to alt-templates and must win.
        colors = tmp_path / "colors.yaml"
        colors.write_text("special:\n  background: '#000000'\ncolors: []\n")
        override_templates = tmp_path / "alt-templates"
        (override_templates / "battery").mkdir(parents=True)
        (override_templates / "battery" / "battery-0.svg").write_text(
            '<svg><path fill="{{background}}"/></svg>'
        )
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
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
            ["render", str(icons), "--template-dir", str(override_templates)],
        )
        assert result.exit_code == 0, result.stderr
        out = tmp_path / "out" / "override" / "battery-0.svg"
        assert out.exists()

    def test_relative_template_dir_joins_global_root(
        self, cli_deps_integration, integration_env, tmp_path, monkeypatch
    ):
        colors = tmp_path / "colors.yaml"
        colors.write_text("special:\n  background: '#000000'\ncolors: []\n")
        sub = tmp_path / "sub-templates"
        (sub / "battery").mkdir(parents=True)
        (sub / "battery" / "battery-0.svg").write_text('<svg><path fill="{{background}}"/></svg>')
        # Point the templates root at the sub-templates dir.
        monkeypatch.setenv("ICON_RENDERER__TEMPLATES__DIR", str(sub))
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "battery:\n"
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
