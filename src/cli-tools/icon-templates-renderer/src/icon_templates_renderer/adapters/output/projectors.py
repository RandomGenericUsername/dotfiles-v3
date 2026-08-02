from __future__ import annotations

from typing import Any

from cli_output.domain.views import CustomView, ErrorView, MessageView
from rich.console import Console
from rich.text import Text

from icon_templates_renderer.domain.exceptions import IconRendererError
from icon_templates_renderer.domain.models import ListResult, RenderResult, ValidateResult


def _render_object(result: RenderResult) -> dict[str, Any]:
    return {
        "success": result.success,
        "output_files": [str(v.output_path) for v in result.rendered],
    }


def project_render_result(result: RenderResult) -> CustomView:
    lines = [f"Rendered: {v.output_path}" for v in result.rendered]
    lines.append("")
    lines.append(f"{len(result.rendered)} icon(s) rendered.")

    def rich(console: Console) -> None:
        console.print()
        console.print(
            Text(
                "Success" if result.success else "Failure",
                style="bold green" if result.success else "bold red",
            )
        )
        for v in result.rendered:
            console.print(f"Rendered: {v.output_path}")
        console.print()
        console.print(f"{len(result.rendered)} icon(s) rendered.")
        console.print()

    return CustomView(plain="\n".join(lines), object=_render_object(result), rich=rich)


def project_list_result(result: ListResult) -> CustomView:
    if result.single:
        name, variants = result.groups[0]
        lines = ["Variants:"]
        lines.extend(f"  - {v}" for v in variants)
        obj: dict[str, Any] = {"icon": name, "variants": list(variants)}
    else:
        lines = []
        obj = {"groups": {}}
        for name, variants in result.groups:
            lines.append(f"{name}:")
            lines.extend(f"  - {v}" for v in variants)
            obj["groups"][name] = list(variants)

    def rich(console: Console) -> None:
        console.print()
        for name, variants in result.groups:
            console.print(Text(name, style="bold"))
            for v in variants:
                console.print(f"  - {v}")
        console.print()

    return CustomView(plain="\n".join(lines), object=obj, rich=rich)


def project_validate_result(result: ValidateResult) -> CustomView:
    obj = {
        "ok": result.ok,
        "checked_groups": result.checked_groups,
        "checked_variants": result.checked_variants,
    }
    return CustomView(
        plain="Validation passed.",
        object=obj,
        rich="[bold green]Validation passed.[/bold green]",
    )


def project_message(msg: str) -> MessageView:
    return MessageView(text=msg)


def project_error(exc: IconRendererError) -> ErrorView:
    return ErrorView(kind=type(exc).__name__, message=str(exc), details={})
