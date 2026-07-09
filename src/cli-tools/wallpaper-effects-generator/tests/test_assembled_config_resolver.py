from __future__ import annotations

from pathlib import Path

import pytest
from config_assembler_engine import ConfigAssemblerError

from wallpaper_effects_generator.adapters.assembled_config_resolver import (
    AssembledConfigResolver,
)
from wallpaper_effects_generator.domain.enums import RuntimeMode, Verbosity
from wallpaper_effects_generator.ports.config_resolver import ConfigResolverPort


def test_is_config_resolver_port():
    assert isinstance(AssembledConfigResolver(), ConfigResolverPort)


def test_resolve_uses_explicit_path(tmp_path: Path):
    config_file = tmp_path / "settings.toml"
    config_file.write_text("""
version = "1.0"

[execution]
parallel = false
strict = true
max_workers = 2

[output]
verbosity = 2
directory = "/tmp/test-out"

[backend]
binary = "convert"

[runtime]
mode = "container"

[container]
engine = "podman"
image_tag = "test-v1"
image_registry = "myreg.io"
""")

    resolver = AssembledConfigResolver()
    settings = resolver.resolve(explicit_path=config_file)

    assert settings.version == "1.0"
    assert settings.execution.parallel is False
    assert settings.execution.strict is True
    assert settings.execution.max_workers == 2
    assert settings.output.verbosity == Verbosity.VERBOSE
    assert settings.backend.binary == "convert"
    assert settings.runtime.mode == RuntimeMode.CONTAINER
    assert settings.container.engine == "podman"
    assert settings.container.image_tag == "test-v1"
    assert settings.container.image_registry == "myreg.io"
    assert resolver.get_resolved_path() == config_file.resolve()


def test_resolve_unknown_mode_defaults_to_local(tmp_path: Path):
    config_file = tmp_path / "settings.toml"
    config_file.write_text("""
version = "1.0"
[execution]
[runtime]
mode = "unknown"
[container]
""")

    resolver = AssembledConfigResolver()
    settings = resolver.resolve(explicit_path=config_file)

    assert isinstance(settings.runtime.mode, RuntimeMode)
    assert settings.runtime.mode == RuntimeMode.LOCAL


def test_resolve_minimal_config(tmp_path: Path):
    config_file = tmp_path / "settings.toml"
    config_file.write_text('version = "1.0"\n')

    resolver = AssembledConfigResolver()
    settings = resolver.resolve(explicit_path=config_file)

    assert settings.version == "1.0"
    assert settings.execution.parallel is True
    assert settings.execution.max_workers == 4
    assert settings.output.verbosity == Verbosity.NORMAL
    assert settings.container.engine == "docker"


def test_get_resolved_path_none_before_resolve():
    resolver = AssembledConfigResolver()
    assert resolver.get_resolved_path() is None


def test_resolve_file_not_found(tmp_path: Path):
    resolver = AssembledConfigResolver()
    nonexistent = tmp_path / "nonexistent.toml"

    with pytest.raises(ConfigAssemblerError):
        resolver.resolve(explicit_path=nonexistent)
