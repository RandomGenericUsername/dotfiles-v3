from __future__ import annotations

from importlib.metadata import version as dist_version

from cli_invocation_contract import CONTRACT_VERSION
from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app


def test_version_flag_reports_package_and_contract_version() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == (
        f"{dist_version('icon-templates-renderer')} contract {CONTRACT_VERSION}"
    )
