from pathlib import Path

from config_assembler_engine.adapters.strategies.cli_path import CliPathStrategy
from config_assembler_engine.adapters.strategies.default_file import DefaultFileStrategy
from config_assembler_engine.adapters.strategies.directory import DirectoryTraversalStrategy
from config_assembler_engine.adapters.strategies.env_path import EnvPathStrategy
from config_assembler_engine.adapters.strategies.xdg import XdgStrategy
from config_assembler_engine.domain.models import PathSource, ResolutionPolicy, ResolvedPath


class TestCliPathStrategy:
    def test_returns_none_if_no_path(self):
        strategy = CliPathStrategy()
        result = strategy.resolve(ResolutionPolicy(env_prefix=""), explicit_path=None)
        assert result is None

    def test_returns_none_if_path_does_not_exist(self):
        strategy = CliPathStrategy()
        result = strategy.resolve(
            ResolutionPolicy(env_prefix=""), explicit_path="/nonexistent/path.yaml"
        )
        assert result is None

    def test_returns_resolved_path_if_exists(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: val")
        strategy = CliPathStrategy()
        result = strategy.resolve(
            ResolutionPolicy(env_prefix=""), explicit_path=str(config_file)
        )
        assert result is not None
        assert result.path == config_file.resolve()
        assert result.source == PathSource.CLI_PATH

    def test_expands_user_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: val")
        strategy = CliPathStrategy()
        result = strategy.resolve(
            ResolutionPolicy(env_prefix=""), explicit_path="~/config.yaml"
        )
        assert result is not None
        assert result.source == PathSource.CLI_PATH


class TestEnvPathStrategy:
    def test_returns_none_if_env_not_set(self, monkeypatch):
        monkeypatch.delenv("TEST_ENV_VAR", raising=False)
        strategy = EnvPathStrategy(var="TEST_ENV_VAR")
        result = strategy.resolve(ResolutionPolicy(env_prefix="MY_APP"))
        assert result is None

    def test_returns_none_if_path_does_not_exist(self, monkeypatch):
        monkeypatch.setenv("MY_APP_TEST_ENV_VAR", "/nonexistent.yaml")
        strategy = EnvPathStrategy(var="TEST_ENV_VAR")
        result = strategy.resolve(ResolutionPolicy(env_prefix="MY_APP"))
        assert result is None

    def test_returns_resolved_path_if_exists(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: val")
        monkeypatch.setenv("MY_APP_CONFIG_PATH", str(config_file))
        strategy = EnvPathStrategy(var="CONFIG_PATH")
        result = strategy.resolve(ResolutionPolicy(env_prefix="MY_APP"))
        assert result is not None
        assert result.path == config_file.resolve()
        assert result.source == PathSource.ENV_PATH

    def test_default_var_name(self):
        strategy = EnvPathStrategy()
        assert strategy._var == "CONFIG_FILE_PATH"


class TestDirectoryTraversalStrategy:
    def test_returns_none_if_not_found(self, tmp_path):
        strategy = DirectoryTraversalStrategy(filename="nonexistent.yaml", max_levels=0)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is None

    def test_finds_file_in_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: val")
        strategy = DirectoryTraversalStrategy(filename="config.yaml", max_levels=0)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is not None
        assert result.path == config_file.resolve()
        assert result.source == PathSource.DIRECTORY

    def test_finds_file_in_parent(self, tmp_path, monkeypatch):
        child = tmp_path / "child"
        child.mkdir()
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: val")
        monkeypatch.chdir(child)
        strategy = DirectoryTraversalStrategy(filename="config.yaml", max_levels=1)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is not None
        assert result.path == config_file.resolve()

    def test_cwd_takes_priority_over_parent(self, tmp_path, monkeypatch):
        child = tmp_path / "child"
        child.mkdir()
        cwd_config = child / "config.yaml"
        cwd_config.write_text("key: cwd")
        parent_config = tmp_path / "config.yaml"
        parent_config.write_text("key: parent")
        monkeypatch.chdir(child)
        strategy = DirectoryTraversalStrategy(filename="config.yaml", max_levels=1)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is not None
        assert result.path == cwd_config.resolve()


class TestXdgStrategy:
    def test_returns_none_if_subdir_empty(self):
        strategy = XdgStrategy(xdg_subdir="", filename="config.yaml")
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is None

    def test_returns_none_if_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        strategy = XdgStrategy(xdg_subdir="my-app", filename="nonexistent.yaml")
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is None

    def test_finds_file_in_xdg_config_home(self, tmp_path, monkeypatch):
        xdg_dir = tmp_path / ".config" / "my-app"
        xdg_dir.mkdir(parents=True)
        config_file = xdg_dir / "config.yaml"
        config_file.write_text("key: val")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        strategy = XdgStrategy(xdg_subdir="my-app", filename="config.yaml")
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is not None
        assert result.path == config_file.resolve()
        assert result.source == PathSource.XDG

    def test_falls_back_to_home_config(self, tmp_path, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        xdg_dir = tmp_path / ".config" / "my-app"
        xdg_dir.mkdir(parents=True)
        config_file = xdg_dir / "config.yaml"
        config_file.write_text("key: val")
        strategy = XdgStrategy(xdg_subdir="my-app", filename="config.yaml")
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is not None
        assert result.source == PathSource.XDG


class TestDefaultFileStrategy:
    def test_returns_none_if_not_found(self):
        strategy = DefaultFileStrategy(path=Path("/nonexistent/default.yaml"))
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is None

    def test_returns_resolved_path_if_exists(self, tmp_path):
        config_file = tmp_path / "default.yaml"
        config_file.write_text("key: val")
        strategy = DefaultFileStrategy(path=config_file)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is not None
        assert result.path == config_file.resolve()
        assert result.source == PathSource.DEFAULT
