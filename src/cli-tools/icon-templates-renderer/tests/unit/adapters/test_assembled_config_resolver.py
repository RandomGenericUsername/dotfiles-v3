from __future__ import annotations

from icon_templates_renderer.adapters.assembled_config_resolver import AssembledConfigResolver
from icon_templates_renderer.domain.enums import Verbosity


class TestAssembledConfigResolver:
    def test_resolves_bundled_default(self) -> None:
        settings = AssembledConfigResolver().resolve()
        assert settings.output.verbosity is Verbosity.NORMAL

    def test_cli_override_honored(self) -> None:
        settings = AssembledConfigResolver().resolve(
            cli_overrides={"output.verbosity": str(Verbosity.VERBOSE.value)}
        )
        assert settings.output.verbosity is Verbosity.VERBOSE

    def test_get_resolved_path_after_resolve(self) -> None:
        resolver = AssembledConfigResolver()
        resolver.resolve()
        assert resolver.get_resolved_path() is not None
