"""Typer CLI — the composition root (outer shell) of the provisioning hexagon.

This is the only production place that constructs ``AnsibleExecutor`` /
``AnsibleFactReader`` and wires them into the use cases (Story 1.8 deferred
wiring from Stories 1.6/1.7). The callback builds a ``CliDependencies`` bag
on ``ctx.obj`` and every command renders through the shared ``_render_run``
helper: ``ResultView`` on success (including the resolved install dir), a
structured ``ErrorView`` + non-zero exit on the four known adapter/domain
errors or a failed run, and uncaught propagation for anything unexpected.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

import typer
from cli_output.adapters.factory import create_renderer
from cli_output.domain.enums import OutputFormat
from cli_output.domain.views import CustomView, ErrorView, ResultView
from cli_output.ports.renderer import Renderer

from provisioning.adapters.ansible_executor import (
    AnsibleExecutor,
    ProvisionExecutorError,
    ProvisionTimeoutError,
)
from provisioning.adapters.ansible_fact_reader import (
    AnsibleFactReader,
    InvalidFactOutputError,
    UnknownOsFamilyError,
)
from provisioning.application import (
    BootstrapUseCase,
    ProvisionMachineUseCase,
    VerifyCapabilityUseCase,
    resolve_install_dir,
)
from provisioning.cli.options import CHECK_OPT, OUTPUT_FORMAT_OPT
from provisioning.domain.models import ProvisionResult

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


@dataclass
class CliDependencies:
    plan: ProvisionMachineUseCase
    apply: ProvisionMachineUseCase
    verify: VerifyCapabilityUseCase
    bootstrap: BootstrapUseCase


# main.py lives at src/provisioning/src/provisioning/cli/main.py:
#   parents[0]=cli, parents[1]=provisioning, parents[2]=src, parents[3]=src/provisioning
_ANSIBLE_ROOT = Path(__file__).resolve().parents[3] / "ansible"


def build_deps() -> CliDependencies:
    executor = AnsibleExecutor(
        inventory=_ANSIBLE_ROOT / "inventory" / "localhost.yaml",
        tags="all",
    )
    fact_reader = AnsibleFactReader()
    bootstrap_playbook = _ANSIBLE_ROOT / "playbooks" / "bootstrap.yaml"
    verify_playbook = _ANSIBLE_ROOT / "playbooks" / "verify.yaml"
    return CliDependencies(
        plan=ProvisionMachineUseCase(executor, fact_reader, bootstrap_playbook),
        apply=ProvisionMachineUseCase(executor, fact_reader, bootstrap_playbook),
        verify=VerifyCapabilityUseCase(executor, fact_reader, verify_playbook),
        bootstrap=BootstrapUseCase(executor, fact_reader, bootstrap_playbook),
    )


@app.callback()
def main_callback(
    ctx: typer.Context,
    output_format: OutputFormat = OUTPUT_FORMAT_OPT,
) -> None:
    ctx.obj = {
        "renderer": create_renderer(output_format),
        "deps": build_deps(),
    }


def _render_run(
    renderer: Renderer,
    fn: Callable[[], ProvisionResult],
    command: str,
) -> None:
    try:
        result = fn()
    except (
        ProvisionExecutorError,
        ProvisionTimeoutError,
        UnknownOsFamilyError,
        InvalidFactOutputError,
    ) as exc:
        renderer.error(ErrorView(kind=type(exc).__name__, message=str(exc)))
        raise typer.Exit(code=1) from None
    if not result.success:
        renderer.error(
            ErrorView(
                kind="ProvisionFailed",
                message=f"{command} failed (returncode={result.returncode})",
                details={"stderr": result.stderr},
            )
        )
        raise typer.Exit(code=1) from None
    renderer.result(
        ResultView(
            success=True,
            title=command,
            fields={
                "command": command,
                "install_dir": str(resolve_install_dir()),
                "returncode": result.returncode,
                "tasks": dict(result.tasks),
            },
        )
    )


@app.command(help="Diff desired machine state against actual state (Ansible --check)")
def plan(ctx: typer.Context) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    renderer: Renderer = ctx.obj["renderer"]
    _render_run(renderer, lambda: deps.plan.provision(check=True), "plan")


@app.command(help="Apply provisioning idempotently")
def apply(ctx: typer.Context) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    renderer: Renderer = ctx.obj["renderer"]
    _render_run(renderer, lambda: deps.apply.provision(check=False), "apply")


@app.command(help="Assert all done-criteria hold")
def verify(ctx: typer.Context) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    renderer: Renderer = ctx.obj["renderer"]
    _render_run(renderer, lambda: deps.verify.verify(), "verify")


@app.command(help="Run the aggregate provisioning end-to-end")
def bootstrap(
    ctx: typer.Context,
    check: bool = CHECK_OPT,
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    renderer: Renderer = ctx.obj["renderer"]
    _render_run(renderer, lambda: deps.bootstrap.bootstrap(check=check), "bootstrap")


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
