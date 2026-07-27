from pathlib import Path

import pytest

from config_assembler_engine.adapters.strategies.cli_path import CliDirStrategy, CliPathStrategy
from config_assembler_engine.adapters.strategies.default_file import DefaultDirStrategy, DefaultFileStrategy
from config_assembler_engine.adapters.strategies.directory import DirTraversalStrategy, DirectoryTraversalStrategy
from config_assembler_engine.adapters.strategies.env_path import EnvDirStrategy, EnvPathStrategy
from config_assembler_engine.adapters.strategies.xdg import XdgDirStrategy, XdgStrategy
from config_assembler_engine.application.use_cases import AssembleDir
from config_assembler_engine.domain.models import DirAssemblyResult, PathSource, ResolutionPolicy, ResourceKind, ResolvedPath


class TestCliPathStrategy:
    def test_returns_none_if_no_path(self):
        strategy = CliPathStrategy(kind=ResourceKind.FILE)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""), explicit_path=None)
        assert result is None

    def test_returns_none_if_path_does_not_exist(self):
        strategy = CliPathStrategy(kind=ResourceKind.FILE)
        result = strategy.resolve(
            ResolutionPolicy(env_prefix=""), explicit_path="/nonexistent/path.yaml"
        )
        assert result is None

    def test_returns_resolved_path_if_exists(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: val")
        strategy = CliPathStrategy(kind=ResourceKind.FILE)
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
        strategy = CliPathStrategy(kind=ResourceKind.FILE)
        result = strategy.resolve(
            ResolutionPolicy(env_prefix=""), explicit_path="~/config.yaml"
        )
        assert result is not None
        assert result.source == PathSource.CLI_PATH


class TestEnvPathStrategy:
    def test_returns_none_if_env_not_set(self, monkeypatch):
        monkeypatch.delenv("TEST_ENV_VAR", raising=False)
        strategy = EnvPathStrategy(var="TEST_ENV_VAR", kind=ResourceKind.FILE)
        result = strategy.resolve(ResolutionPolicy(env_prefix="MY_APP"))
        assert result is None

    def test_returns_none_if_path_does_not_exist(self, monkeypatch):
        monkeypatch.setenv("MY_APP_TEST_ENV_VAR", "/nonexistent.yaml")
        strategy = EnvPathStrategy(var="TEST_ENV_VAR", kind=ResourceKind.FILE)
        result = strategy.resolve(ResolutionPolicy(env_prefix="MY_APP"))
        assert result is None

    def test_returns_resolved_path_if_exists(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: val")
        monkeypatch.setenv("MY_APP_CONFIG_PATH", str(config_file))
        strategy = EnvPathStrategy(var="CONFIG_PATH", kind=ResourceKind.FILE)
        result = strategy.resolve(ResolutionPolicy(env_prefix="MY_APP"))
        assert result is not None
        assert result.path == config_file.resolve()
        assert result.source == PathSource.ENV_PATH

    def test_default_var_name(self):
        strategy = EnvPathStrategy(kind=ResourceKind.FILE)
        assert strategy._var == "CONFIG_FILE_PATH"


class TestDirectoryTraversalStrategy:
    def test_returns_none_if_not_found(self, tmp_path):
        strategy = DirectoryTraversalStrategy(filename="nonexistent.yaml", max_levels=0, kind=ResourceKind.FILE)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is None

    def test_finds_file_in_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: val")
        strategy = DirectoryTraversalStrategy(filename="config.yaml", max_levels=0, kind=ResourceKind.FILE)
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
        strategy = DirectoryTraversalStrategy(filename="config.yaml", max_levels=1, kind=ResourceKind.FILE)
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
        strategy = DirectoryTraversalStrategy(filename="config.yaml", max_levels=1, kind=ResourceKind.FILE)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is not None
        assert result.path == cwd_config.resolve()


class TestXdgStrategy:
    def test_returns_none_if_subdir_empty(self):
        strategy = XdgStrategy(xdg_subdir="", filename="config.yaml", kind=ResourceKind.FILE)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is None

    def test_returns_none_if_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        strategy = XdgStrategy(xdg_subdir="my-app", filename="nonexistent.yaml", kind=ResourceKind.FILE)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is None

    def test_finds_file_in_xdg_config_home(self, tmp_path, monkeypatch):
        xdg_dir = tmp_path / ".config" / "my-app"
        xdg_dir.mkdir(parents=True)
        config_file = xdg_dir / "config.yaml"
        config_file.write_text("key: val")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        strategy = XdgStrategy(xdg_subdir="my-app", filename="config.yaml", kind=ResourceKind.FILE)
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
        strategy = XdgStrategy(xdg_subdir="my-app", filename="config.yaml", kind=ResourceKind.FILE)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is not None
        assert result.source == PathSource.XDG


class TestDefaultFileStrategy:
    def test_returns_none_if_not_found(self):
        strategy = DefaultFileStrategy(path=Path("/nonexistent/default.yaml"), kind=ResourceKind.FILE)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is None

    def test_returns_resolved_path_if_exists(self, tmp_path):
        config_file = tmp_path / "default.yaml"
        config_file.write_text("key: val")
        strategy = DefaultFileStrategy(path=config_file, kind=ResourceKind.FILE)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is not None
        assert result.path == config_file.resolve()
        assert result.source == PathSource.DEFAULT


class TestCliDirStrategy:
    def test_resolves_directory(self, tmp_path):
        strategy = CliDirStrategy()
        result = strategy.resolve(
            ResolutionPolicy(env_prefix=""), explicit_path=str(tmp_path)
        )
        assert result is not None
        assert result.path == tmp_path.resolve()
        assert result.source == PathSource.CLI_PATH
        assert result.kind == ResourceKind.DIRECTORY

    def test_rejects_file(self, tmp_path):
        config_file = tmp_path / "file.yaml"
        config_file.write_text("key: val")
        strategy = CliDirStrategy()
        result = strategy.resolve(
            ResolutionPolicy(env_prefix=""), explicit_path=str(config_file)
        )
        assert result is None


class TestEnvDirStrategy:
    def test_resolves_directory(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_APP_TEMPLATES_DIR", str(tmp_path))
        strategy = EnvDirStrategy(var="TEMPLATES_DIR")
        result = strategy.resolve(ResolutionPolicy(env_prefix="MY_APP"))
        assert result is not None
        assert result.path == tmp_path.resolve()
        assert result.source == PathSource.ENV_PATH
        assert result.kind == ResourceKind.DIRECTORY

    def test_rejects_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "file.yaml"
        config_file.write_text("key: val")
        monkeypatch.setenv("MY_APP_TEMPLATES_DIR", str(config_file))
        strategy = EnvDirStrategy(var="TEMPLATES_DIR")
        result = strategy.resolve(ResolutionPolicy(env_prefix="MY_APP"))
        assert result is None


class TestDirTraversalStrategy:
    def test_resolves_directory_in_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        subdir = tmp_path / "templates"
        subdir.mkdir()
        strategy = DirTraversalStrategy(dirname="templates", max_levels=0)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is not None
        assert result.path == subdir.resolve()
        assert result.source == PathSource.DIRECTORY
        assert result.kind == ResourceKind.DIRECTORY


class TestXdgDirStrategy:
    def test_resolves_directory(self, tmp_path, monkeypatch):
        xdg_dir = tmp_path / ".config" / "my-app" / "templates"
        xdg_dir.mkdir(parents=True)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        strategy = XdgDirStrategy(xdg_subdir="my-app", dirname="templates")
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is not None
        assert result.path == xdg_dir.resolve()
        assert result.source == PathSource.XDG
        assert result.kind == ResourceKind.DIRECTORY


class TestDefaultDirStrategy:
    def test_resolves_directory(self, tmp_path):
        strategy = DefaultDirStrategy(path=tmp_path)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is not None
        assert result.path == tmp_path.resolve()
        assert result.source == PathSource.DEFAULT
        assert result.kind == ResourceKind.DIRECTORY

    def test_rejects_file(self, tmp_path):
        config_file = tmp_path / "file.yaml"
        config_file.write_text("key: val")
        strategy = DefaultDirStrategy(path=config_file)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is None


class TestKindEnforcement:
    def test_file_strategy_rejects_directory(self, tmp_path):
        strategy = DefaultFileStrategy(path=tmp_path, kind=ResourceKind.FILE)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is None

    def test_dir_strategy_rejects_file(self, tmp_path):
        config_file = tmp_path / "file.yaml"
        config_file.write_text("key: val")
        strategy = DefaultDirStrategy(path=config_file)
        result = strategy.resolve(ResolutionPolicy(env_prefix=""))
        assert result is None


class TestAssembleDir:
    def test_resolves_directory_and_lists_files(self, tmp_path):
        (tmp_path / "template.j2").write_text("a")
        (tmp_path / "other.j2").write_text("b")
        (tmp_path / "readme.md").write_text("c")
        strategies = [DefaultDirStrategy(path=tmp_path)]
        use_case = AssembleDir(
            path_resolver=type("MockResolver", (), {"resolve": lambda s, p, explicit_path=None: ResolvedPath(path=tmp_path, source=PathSource.DEFAULT, kind=ResourceKind.DIRECTORY)})(),
            file_pattern="*.j2",
        )
        result = use_case.execute(ResolutionPolicy(env_prefix=""))
        assert isinstance(result, DirAssemblyResult)
        assert result.directory == tmp_path.resolve()
        assert all(f.name in {"template.j2", "other.j2"} for f in result.files)
        assert len(result.files) == 2

    def test_raises_when_path_is_not_directory(self, tmp_path):
        config_file = tmp_path / "file.yaml"
        config_file.write_text("key: val")
        strategies = [DefaultFileStrategy(path=config_file, kind=ResourceKind.FILE)]
        from config_assembler_engine.errors import NotADirectoryError_
        use_case = AssembleDir(
            path_resolver=type("MockResolver", (), {"resolve": lambda s, p, explicit_path=None: ResolvedPath(path=config_file, source=PathSource.DEFAULT, kind=ResourceKind.FILE)})(),
            file_pattern="*",
        )
        with pytest.raises(NotADirectoryError_):
            use_case.execute(ResolutionPolicy(env_prefix=""))

    def test_raises_when_no_strategy_matches(self, tmp_path):
        from config_assembler_engine.errors import PathResolutionError
        resolve = lambda s, p, explicit_path=None: (_ for _ in ()).throw(PathResolutionError("no match"))
        use_case = AssembleDir(
            path_resolver=type("MockResolver", (), {"resolve": resolve})(),
            file_pattern="*",
        )
        with pytest.raises(PathResolutionError):
            use_case.execute(ResolutionPolicy(env_prefix=""))
