from __future__ import annotations

from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


class TestColorMappingsIntegration:
    def test_semantic_placeholder_names_resolve(self, cli_deps_integration, tmp_path):
        colors = tmp_path / "colors.yaml"
        colors.write_text(
            'special:\n  background: "#1a1a2e"\n  foreground: "#e0e0e0"\ncolors: []\n'
        )
        template_dir = tmp_path / "templates" / "semantic"
        template_dir.mkdir(parents=True)
        (template_dir / "default.svg").write_text(
            '<svg><path fill="{{icon_fill}}" stroke="{{icon_border}}"/></svg>'
        )
        icons = tmp_path / "icons.yaml"
        icons.write_text(
            "semantic:\n"
            f"  color_scheme: {colors}\n"
            "  template_dir: templates/semantic/\n"
            "  output_dir: out/semantic/\n"
            "  color_mappings:\n"
            "    icon_fill: background\n"
            "    icon_border: foreground\n"
            "  variants:\n"
            "    - name: default\n"
            "      template: default.svg\n"
            "      output: default.svg\n"
        )
        result = CliRunner().invoke(app, ["render", str(icons)])
        assert result.exit_code == 0, result.stderr
        out = tmp_path / "out" / "semantic" / "default.svg"
        assert out.exists()
        rendered = out.read_text()
        assert "#1a1a2e" in rendered
        assert "{{" not in rendered
