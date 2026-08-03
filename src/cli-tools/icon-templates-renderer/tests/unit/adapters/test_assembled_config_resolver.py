from __future__ import annotations

from pathlib import Path

from icon_templates_renderer.adapters.assembled_config_resolver import AssembledConfigResolver
from icon_templates_renderer.domain.enums import Verbosity


class TestAssembledConfigResolver:
    def test_resolves_bundled_default(self) -> None:
        settings = AssembledConfigResolver().resolve()
        assert settings.output.verbosity is Verbosity.NORMAL
        assert settings.output.output_dir == Path("/tmp/icon-templates-renderer")
        assert settings.templates.dir is None
        assert settings.color_scheme.path is None

    def test_cli_override_honored(self) -> None:
        settings = AssembledConfigResolver().resolve(
            cli_overrides={"output.verbosity": str(Verbosity.VERBOSE.value)}
        )
        assert settings.output.verbosity is Verbosity.VERBOSE

    def test_cli_output_dir_override_honored(self) -> None:
        settings = AssembledConfigResolver().resolve(
            cli_overrides={"output.output_dir": "/tmp/custom"}
        )
        assert settings.output.output_dir == Path("/tmp/custom")

    def test_cli_templates_dir_override_honored(self) -> None:
        settings = AssembledConfigResolver().resolve(cli_overrides={"templates.dir": "/t"})
        assert settings.templates.dir == Path("/t")

    def test_cli_color_scheme_override_honored(self) -> None:
        settings = AssembledConfigResolver().resolve(cli_overrides={"color_scheme.path": "/c.yaml"})
        assert settings.color_scheme.path == Path("/c.yaml")

    def test_get_resolved_path_after_resolve(self) -> None:
        resolver = AssembledConfigResolver()
        resolver.resolve()
        assert resolver.get_resolved_path() is not None
