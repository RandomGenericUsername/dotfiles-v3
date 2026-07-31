from __future__ import annotations

from pathlib import Path

import pytest

from config_assembler_engine import ConfigAssemblerError

from wallpaper_effects_generator.adapters.assembled_config_resolver import (
    AssembledConfigResolver,
)


def test_cli_path_prevails_over_env_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / "env_settings.toml"
    env_path.write_text('version = "1.0"\n[execution]\n[runtime]\nmode = "local"\n[container]\n')
    cli_path = tmp_path / "cli_settings.toml"
    cli_path.write_text('version = "2.0"\n[execution]\n[runtime]\nmode = "local"\n[container]\n')

    monkeypatch.setenv("WALLPAPER_CONFIG_FILE_PATH", str(env_path))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve(explicit_path=cli_path)

    assert settings.version == "2.0"
    assert resolver.get_resolved_path() == cli_path.resolve()


def test_env_path_takes_second_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / "env_settings.toml"
    env_path.write_text('version = "3.0"\n[execution]\n[runtime]\nmode = "local"\n[container]\n')

    monkeypatch.setenv("WALLPAPER_CONFIG_FILE_PATH", str(env_path))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.version == "3.0"
    assert resolver.get_resolved_path() == env_path.resolve()


def test_cwd_traversal_found_at_depth_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text('version = "4.0"\n[execution]\n[runtime]\nmode = "local"\n[container]\n')

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_empty"))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.version == "4.0"
    assert resolver.get_resolved_path() == config_file.resolve()


def test_cwd_traversal_found_at_depth_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = tmp_path / "level0"
    parent.mkdir()
    config_file = tmp_path / "settings.toml"
    config_file.write_text('version = "5.0"\n[execution]\n[runtime]\nmode = "local"\n[container]\n')

    monkeypatch.chdir(parent)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_empty"))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.version == "5.0"
    assert resolver.get_resolved_path() == config_file.resolve()


def test_cwd_traversal_found_at_depth_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    l1 = tmp_path / "level0" / "level1"
    l1.mkdir(parents=True)
    config_file = tmp_path / "settings.toml"
    config_file.write_text('version = "6.0"\n[execution]\n[runtime]\nmode = "local"\n[container]\n')

    monkeypatch.chdir(l1)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_empty"))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.version == "6.0"
    assert resolver.get_resolved_path() == config_file.resolve()


def test_cwd_traversal_falls_through_at_depth_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deep_dir = tmp_path / "a" / "b" / "c"
    deep_dir.mkdir(parents=True)
    config_file = tmp_path / "settings.toml"
    config_file.write_text('version = "7.0"\n[execution]\n[runtime]\nmode = "local"\n[container]\n')

    monkeypatch.chdir(deep_dir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_empty"))
    resolver = AssembledConfigResolver()
    with pytest.raises(ConfigAssemblerError):
        resolver.resolve()


def test_xdg_resolves_with_custom_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xdg_home = tmp_path / "xdg"
    xdg_weg = xdg_home / "weg"
    xdg_weg.mkdir(parents=True)
    config_file = xdg_weg / "settings.toml"
    config_file.write_text('version = "8.0"\n[execution]\n[runtime]\nmode = "local"\n[container]\n')

    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.version == "8.0"
    assert resolver.get_resolved_path() == config_file.resolve()


def test_xdg_resolves_standard_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    xdg_home = tmp_path / ".config"
    xdg_weg = xdg_home / "weg"
    xdg_weg.mkdir(parents=True)
    config_file = xdg_weg / "settings.toml"
    config_file.write_text('version = "9.0"\n[execution]\n[runtime]\nmode = "local"\n[container]\n')

    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.version == "9.0"
    assert resolver.get_resolved_path() == config_file.resolve()


def test_package_default_fallback_when_no_file_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "nonexistent_xdg"))
    resolver = AssembledConfigResolver()
    with pytest.raises(ConfigAssemblerError):
        resolver.resolve()


def test_wallpaper_section_key_env_override_runtime_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text(
        'version = "1.0"\n[execution]\n[runtime]\nmode = "local"\n[container]\nengine = "docker"\n'
    )
    monkeypatch.setenv("WALLPAPER__RUNTIME__MODE", "container")
    resolver = AssembledConfigResolver()
    settings = resolver.resolve(explicit_path=config_file)
    assert settings.runtime.mode.value == "container"


def test_wallpaper_section_key_env_override_container_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text(
        'version = "1.0"\n[execution]\n[runtime]\nmode = "local"\n[container]\nengine = "docker"\n'
    )
    monkeypatch.setenv("WALLPAPER__CONTAINER__ENGINE", "podman")
    resolver = AssembledConfigResolver()
    settings = resolver.resolve(explicit_path=config_file)
    assert settings.container.engine == "podman"


def test_wallpaper_section_key_env_override_output_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text(
        'version = "1.0"\n[execution]\n[runtime]\nmode = "local"\n[container]\nengine = "docker"\n'
    )
    monkeypatch.setenv("WALLPAPER__OUTPUT__DIRECTORY", "/custom/out")
    resolver = AssembledConfigResolver()
    settings = resolver.resolve(explicit_path=config_file)
    assert settings.output.directory == Path("/custom/out")


def test_cli_overrides_beat_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text(
        'version = "1.0"\n[execution]\n[runtime]\nmode = "local"\n[container]\nengine = "docker"\n'
    )
    monkeypatch.setenv("WALLPAPER__RUNTIME__MODE", "container")
    resolver = AssembledConfigResolver()
    settings = resolver.resolve(explicit_path=config_file, cli_overrides={"runtime.mode": "local"})
    assert settings.runtime.mode.value == "local"
