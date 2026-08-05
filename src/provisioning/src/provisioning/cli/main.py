from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

import typer
from cli_output.adapters.factory import create_renderer
from cli_output.domain.enums import OutputFormat
from cli_output.domain.views import CustomView, ErrorView
from cli_output.ports.renderer import Renderer

app = typer.Typer(
    name="dotfiles-provision",
    help=(
        "Dotfiles machine provisioning orchestrator.\n\n"
        "Establishes the operational environment (packages, CLI tools, assets, "
        "filesystem, settings, palette) that the Phase 2 runtime assumes exists.\n\n"
        "Commands:\n"
        "  plan      Diff desired machine state against actual state (Ansible --check)\n"
        "  apply     Apply provisioning idempotently\n"
        "  verify    Assert all done-criteria hold\n"
        "  bootstrap Run the aggregate provisioning end-to-end"
    ),
)


def _renderer() -> Renderer:
    return create_renderer(OutputFormat.JSON)


@app.callback()
def main_callback(ctx: typer.Context) -> None:
    ctx.obj = {"renderer": _renderer()}


@app.command(help="Show the installed package version")
def version(ctx: typer.Context) -> None:
    try:
        ver = _pkg_version("dotfiles-provision")
    except PackageNotFoundError:
        ctx.obj["renderer"].error(
            ErrorView(
                kind="PackageNotFoundError",
                message="dotfiles-provision package not installed",
            )
        )
        raise typer.Exit(code=1) from None

    ctx.obj["renderer"].custom(CustomView(plain=ver, object={"version": ver}, rich=ver))


if __name__ == "__main__":
    app()
