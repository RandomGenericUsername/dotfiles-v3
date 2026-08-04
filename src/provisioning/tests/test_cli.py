from __future__ import annotations

import json

import typer
from typer.testing import CliRunner

from provisioning.cli.main import app

runner = CliRunner()


class TestVersionCommand:
    def test_version_renders_version_string(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "version" in data

    def test_version_exits_nonzero_when_package_not_installed(self, monkeypatch) -> None:
        import provisioning.cli.main as cli_main

        def _raise(*args, **kwargs):
            from importlib.metadata import PackageNotFoundError

            raise PackageNotFoundError

        monkeypatch.setattr(cli_main, "_pkg_version", _raise)
        result = runner.invoke(app, ["version"])
        assert result.exit_code != 0


class TestAppEntrypoint:
    def test_app_is_typer_app(self) -> None:
        assert isinstance(app, typer.Typer)

    def test_app_name(self) -> None:
        assert app.info.name == "dotfiles-provision"
