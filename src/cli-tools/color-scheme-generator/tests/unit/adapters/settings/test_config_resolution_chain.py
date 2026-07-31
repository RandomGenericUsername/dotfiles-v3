from __future__ import annotations

from pathlib import Path

import pytest

from color_scheme_generator.adapters.settings.config_resolver import (
    AssembledConfigResolver,
)
from color_scheme_generator.domain.enums import Backend, RuntimeMode


@pytest.fixture(autouse=True)
def _clean_ambient_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COLORSCHEME_CONFIG_FILE_PATH", raising=False)


def _write_config(path: Path, directory: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'[output]\ndirectory = "{directory}"\n'
        '[generation]\nbackend = "custom"\n'
        '[runtime]\nmode = "local"\n'
        '[container]\nengine = "docker"\n'
    )
    return path


def test_cli_path_prevails_over_env_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = _write_config(tmp_path / "env_settings.toml", "/prio/env")
    cli_path = _write_config(tmp_path / "cli_settings.toml", "/prio/cli")

    monkeypatch.setenv("COLORSCHEME_CONFIG_FILE_PATH", str(env_path))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve(explicit_path=str(cli_path))

    assert settings.output.directory == Path("/prio/cli")
    assert resolver.last_result is not None
    assert resolver.last_result.resolved_path == cli_path.resolve()


def test_env_path_takes_second_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = _write_config(tmp_path / "env_settings.toml", "/prio/env")

    monkeypatch.setenv("COLORSCHEME_CONFIG_FILE_PATH", str(env_path))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.output.directory == Path("/prio/env")
    assert resolver.last_result is not None
    assert resolver.last_result.resolved_path == env_path.resolve()


def test_cwd_traversal_found_at_depth_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = _write_config(tmp_path / "settings.toml", "/prio/depth0")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_empty"))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.output.directory == Path("/prio/depth0")
    assert resolver.last_result is not None
    assert resolver.last_result.resolved_path == config_file.resolve()


def test_cwd_traversal_found_at_depth_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = tmp_path / "level0"
    parent.mkdir()
    config_file = _write_config(tmp_path / "settings.toml", "/prio/depth1")

    monkeypatch.chdir(parent)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_empty"))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.output.directory == Path("/prio/depth1")
    assert resolver.last_result is not None
    assert resolver.last_result.resolved_path == config_file.resolve()


def test_cwd_traversal_found_at_depth_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deep_dir = tmp_path / "level0" / "level1"
    deep_dir.mkdir(parents=True)
    config_file = _write_config(tmp_path / "settings.toml", "/prio/depth2")

    monkeypatch.chdir(deep_dir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_empty"))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.output.directory == Path("/prio/depth2")
    assert resolver.last_result is not None
    assert resolver.last_result.resolved_path == config_file.resolve()


def test_cwd_traversal_found_at_depth_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deep_dir = tmp_path / "level0" / "level1" / "level2"
    deep_dir.mkdir(parents=True)
    config_file = _write_config(tmp_path / "settings.toml", "/prio/depth3")

    monkeypatch.chdir(deep_dir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_empty"))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.output.directory == Path("/prio/depth3")
    assert resolver.last_result is not None
    assert resolver.last_result.resolved_path == config_file.resolve()


def test_cwd_traversal_depth_4_falls_through_to_xdg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deep_dir = tmp_path / "level0" / "level1" / "level2" / "level3"
    deep_dir.mkdir(parents=True)
    _write_config(tmp_path / "settings.toml", "/prio/depth4-ignored")

    xdg_home = tmp_path / "xdg"
    xdg_file = _write_config(xdg_home / "color-scheme-generator" / "settings.toml", "/prio/xdg")

    monkeypatch.chdir(deep_dir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.output.directory == Path("/prio/xdg")
    assert resolver.last_result is not None
    assert resolver.last_result.resolved_path == xdg_file.resolve()


def test_xdg_resolves_with_custom_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xdg_home = tmp_path / "xdg"
    config_file = _write_config(
        xdg_home / "color-scheme-generator" / "settings.toml", "/prio/xdg-custom"
    )

    empty_cwd = tmp_path / "empty_cwd"
    empty_cwd.mkdir(exist_ok=True)
    monkeypatch.chdir(empty_cwd)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.output.directory == Path("/prio/xdg-custom")
    assert resolver.last_result is not None
    assert resolver.last_result.resolved_path == config_file.resolve()


def test_xdg_resolves_standard_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    xdg_home = tmp_path / ".config"
    config_file = _write_config(
        xdg_home / "color-scheme-generator" / "settings.toml", "/prio/xdg-standard"
    )

    empty_cwd = tmp_path / "empty_cwd"
    empty_cwd.mkdir(exist_ok=True)
    monkeypatch.chdir(empty_cwd)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.output.directory == Path("/prio/xdg-standard")
    assert resolver.last_result is not None
    assert resolver.last_result.resolved_path == config_file.resolve()


def test_package_default_fallback_when_no_file_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty_cwd = tmp_path / "empty_cwd"
    empty_cwd.mkdir(exist_ok=True)
    monkeypatch.chdir(empty_cwd)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "nonexistent_xdg"))
    resolver = AssembledConfigResolver()
    settings = resolver.resolve()

    assert settings.generation.backend is Backend.PYWAL
    assert settings.output.directory == Path("/tmp/color-scheme")


def test_env_section_key_override_runtime_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = _write_config(tmp_path / "settings.toml", "/tmp/base")
    monkeypatch.setenv("COLORSCHEME__RUNTIME__MODE", "container")
    resolver = AssembledConfigResolver()
    settings = resolver.resolve(explicit_path=str(config_file))
    assert settings.runtime.mode is RuntimeMode.CONTAINER


def test_env_section_key_override_container_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = _write_config(tmp_path / "settings.toml", "/tmp/base")
    monkeypatch.setenv("COLORSCHEME__CONTAINER__ENGINE", "podman")
    resolver = AssembledConfigResolver()
    settings = resolver.resolve(explicit_path=str(config_file))
    assert settings.container.engine == "podman"


def test_env_section_key_override_output_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = _write_config(tmp_path / "settings.toml", "/tmp/base")
    monkeypatch.setenv("COLORSCHEME__OUTPUT__DIRECTORY", "/custom/out")
    resolver = AssembledConfigResolver()
    settings = resolver.resolve(explicit_path=str(config_file))
    assert settings.output.directory == Path("/custom/out")


def test_cli_overrides_beat_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = _write_config(tmp_path / "settings.toml", "/tmp/base")
    monkeypatch.setenv("COLORSCHEME__RUNTIME__MODE", "container")
    resolver = AssembledConfigResolver()
    settings = resolver.resolve(
        explicit_path=str(config_file), cli_overrides={"runtime.mode": "local"}
    )
    assert settings.runtime.mode is RuntimeMode.LOCAL
