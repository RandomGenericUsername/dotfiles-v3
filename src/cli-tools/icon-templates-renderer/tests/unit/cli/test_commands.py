from __future__ import annotations

from icon_templates_renderer.cli.main import app
from icon_templates_renderer.domain.exceptions import InvalidYamlError
from icon_templates_renderer.domain.models import ResolvedRoots


class TestRenderCommand:
    def test_render_all_icons(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        result = runner.invoke(app, ["render", str(icons_yaml)])
        assert result.exit_code == 0, result.stderr
        assert fake_icon_renderer.calls[0]["command"] == "render"
        assert fake_icon_renderer.calls[0]["request"].yaml_path == icons_yaml.resolve()

    def test_render_flag_threading(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        runner.invoke(
            app,
            [
                "render",
                str(icons_yaml),
                "--icon",
                "battery",
                "--unsafe",
                "--template-dir",
                str(tmp_path / "tpls"),
                "--color-scheme",
                str(tmp_path / "colors.yaml"),
                "--output-dir",
                str(tmp_path / "out"),
            ],
        )
        request = fake_icon_renderer.calls[0]["request"]
        assert request.icon == "battery"
        assert request.unsafe is True
        roots: ResolvedRoots = request.roots
        assert roots.template_root == (tmp_path / "tpls").resolve()
        assert roots.color_scheme == (tmp_path / "colors.yaml").resolve()
        assert roots.output_root == (tmp_path / "out").resolve()

    def test_render_config_flag_threads_settings_path(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        runner.invoke(app, ["render", str(icons_yaml), "--config", str(tmp_path / "s.toml")])
        request = fake_icon_renderer.calls[0]["request"]
        assert request.roots.output_root is not None

    def test_render_error_exits_non_zero(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        fake_icon_renderer.render_error = InvalidYamlError("YAML file not found: /x")
        result = runner.invoke(app, ["render", str(icons_yaml)])
        assert result.exit_code == 1
        assert "Error: YAML file not found: /x" in result.stderr


class TestListCommand:
    def test_list_all(self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path) -> None:
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        result = runner.invoke(app, ["list", str(icons_yaml)])
        assert result.exit_code == 0, result.stderr
        assert fake_icon_renderer.calls[0]["command"] == "list"
        assert fake_icon_renderer.calls[0]["request"].icon is None
        assert "battery:" in result.stdout

    def test_list_icon(self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path) -> None:
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        runner.invoke(app, ["list", str(icons_yaml), "--icon", "battery"])
        assert fake_icon_renderer.calls[0]["request"].icon == "battery"

    def test_list_roots_are_optional(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        result = runner.invoke(app, ["list", str(icons_yaml)])
        assert result.exit_code == 0, result.stderr


class TestValidateCommand:
    def test_validate_passes(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        result = runner.invoke(app, ["validate", str(icons_yaml)])
        assert result.exit_code == 0, result.stderr
        assert fake_icon_renderer.calls[0]["command"] == "validate"
        assert "Validation passed." in result.stdout


class TestMappingShowCommand:
    def test_mapping_show_all(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        result = runner.invoke(app, ["mapping", "show", str(icons_yaml)])
        assert result.exit_code == 0, result.stderr
        assert fake_icon_renderer.calls[0]["command"] == "mapping_show"
        assert fake_icon_renderer.calls[0]["request"].icon is None

    def test_mapping_show_flag_threading(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        result = runner.invoke(
            app,
            [
                "mapping",
                "show",
                str(icons_yaml),
                "--icon",
                "battery",
                "--template-dir",
                str(tmp_path / "tpls"),
                "--color-scheme",
                str(tmp_path / "colors.yaml"),
            ],
        )
        assert result.exit_code == 0, result.stderr
        request = fake_icon_renderer.calls[0]["request"]
        assert request.icon == "battery"
        assert request.roots.template_root == (tmp_path / "tpls").resolve()
        assert request.roots.color_scheme == (tmp_path / "colors.yaml").resolve()

    def test_mapping_show_error_exits_non_zero(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        from icon_templates_renderer.domain.exceptions import InvalidYamlError

        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        fake_icon_renderer.mapping_show_error = InvalidYamlError("YAML file not found: /x")
        result = runner.invoke(app, ["mapping", "show", str(icons_yaml)])
        assert result.exit_code == 1
        assert "Error: YAML file not found: /x" in result.stderr


class TestMappingSetCommand:
    def test_mapping_set_threads_flags(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        result = runner.invoke(
            app,
            [
                "mapping",
                "set",
                str(icons_yaml),
                "--icon",
                "battery",
                "--placeholder",
                "COLOR_ACCENT",
                "--token",
                "color10",
                "--variant",
                "battery-0",
                "--dry-run",
                "--diff",
                "--unsafe",
            ],
        )
        assert result.exit_code == 0, result.stderr
        call = fake_icon_renderer.calls[0]
        assert call["command"] == "mapping_set"
        request = call["request"]
        assert (request.group, request.placeholder, request.token) == (
            "battery",
            "COLOR_ACCENT",
            "color10",
        )
        assert request.variant == "battery-0"
        assert request.dry_run is True
        assert request.show_diff is True
        assert request.unsafe is True

    def test_mapping_set_requires_icon(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        result = runner.invoke(
            app,
            ["mapping", "set", str(icons_yaml), "--placeholder", "K", "--token", "v"],
        )
        assert result.exit_code == 1
        assert not fake_icon_renderer.calls

    def test_mapping_set_error_exits_non_zero(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        from icon_templates_renderer.domain.exceptions import UnknownTokenError

        icons_yaml = tmp_path / "icons.yaml"
        icons_yaml.write_text("battery: {}\n")
        fake_icon_renderer.mapping_set_error = UnknownTokenError("surface")
        result = runner.invoke(
            app,
            [
                "mapping",
                "set",
                str(icons_yaml),
                "--icon",
                "battery",
                "--placeholder",
                "K",
                "--token",
                "surface",
            ],
        )
        assert result.exit_code == 1
        assert "Error: Token 'surface'" in result.stderr


class TestMappingSetDefaultCommand:
    def test_set_default_threads_flags(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        defaults_yaml = tmp_path / "defaults.yaml"
        defaults_yaml.write_text("defaults: {}\n")
        result = runner.invoke(
            app,
            [
                "mapping",
                "set-default",
                str(defaults_yaml),
                "--placeholder",
                "COLOR_ACCENT",
                "--token",
                "color10",
                "--icons",
                str(tmp_path / "icons.yaml"),
                "--dry-run",
                "--diff",
            ],
        )
        assert result.exit_code == 0, result.stderr
        call = fake_icon_renderer.calls[0]
        assert call["command"] == "mapping_set_default"
        request = call["request"]
        assert request.placeholder == "COLOR_ACCENT"
        assert request.token == "color10"
        assert request.icons_path == (tmp_path / "icons.yaml").resolve()
        assert request.dry_run is True
        assert request.show_diff is True

    def test_set_default_error_exits_non_zero(
        self, runner, cli_deps_with_renderer, fake_icon_renderer, tmp_path
    ) -> None:
        from icon_templates_renderer.domain.exceptions import UnknownPlaceholderError

        defaults_yaml = tmp_path / "defaults.yaml"
        defaults_yaml.write_text("defaults: {}\n")
        fake_icon_renderer.mapping_set_default_error = UnknownPlaceholderError("NOPE")
        result = runner.invoke(
            app,
            [
                "mapping",
                "set-default",
                str(defaults_yaml),
                "--placeholder",
                "NOPE",
                "--token",
                "color10",
            ],
        )
        assert result.exit_code == 1
        assert "Error: Placeholder 'NOPE'" in result.stderr
