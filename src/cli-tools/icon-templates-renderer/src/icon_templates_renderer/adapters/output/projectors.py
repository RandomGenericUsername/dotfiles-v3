from __future__ import annotations

from typing import Any

from cli_output.domain.views import CustomView, ErrorView, MessageView
from rich.console import Console
from rich.text import Text

from icon_templates_renderer.domain.exceptions import IconRendererError
from icon_templates_renderer.domain.models import (
    ListResult,
    MappingSetDefaultResult,
    MappingSetResult,
    MappingShowResult,
    RenderResult,
    TemplateAnalysis,
    ValidateResult,
)


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


def _mapping_show_object(result: MappingShowResult) -> dict[str, Any]:
    return {
        "groups": [
            {
                "group": group_view.group,
                "variants": [
                    {
                        "variant": variant_view.variant,
                        "template_path": str(variant_view.template_path),
                        "svg_body": variant_view.svg_body,
                        "mappings": [
                            {
                                "placeholder": entry.placeholder,
                                "token": entry.token,
                                "origin": str(entry.origin),
                            }
                            for entry in variant_view.entries
                        ],
                    }
                    for variant_view in group_view.variants
                ],
            }
            for group_view in result.groups
        ],
        "palette": dict(result.palette.values),
        "missing_tokens": list(result.missing_tokens),
        "shadows": {placeholder: list(groups) for placeholder, groups in result.shadows},
    }


def project_mapping_show_result(result: MappingShowResult) -> CustomView:
    lines: list[str] = []
    for group_view in result.groups:
        lines.append(f"{group_view.group}:")
        for variant_view in group_view.variants:
            lines.append(f"  {variant_view.variant} (template: {variant_view.template_path}):")
            for entry in variant_view.entries:
                lines.append(f"    {entry.placeholder}: {entry.token} [{entry.origin}]")
    lines.append("Palette:")
    for token, hex_value in result.palette.values.items():
        lines.append(f"  {token}: {hex_value}")
    if result.missing_tokens:
        lines.append(f"Missing tokens: {', '.join(result.missing_tokens)}")
    else:
        lines.append("Missing tokens: none")
    if result.shadows:
        lines.append("Shadowing groups:")
        for placeholder, groups in result.shadows:
            lines.append(f"  {placeholder}: {', '.join(groups)}")
    else:
        lines.append("Shadowing groups: none")

    def rich(console: Console) -> None:
        console.print()
        for group_view in result.groups:
            console.print(Text(group_view.group, style="bold"))
            for variant_view in group_view.variants:
                console.print(f"  {variant_view.variant} (template: {variant_view.template_path})")
                for entry in variant_view.entries:
                    console.print(f"    {entry.placeholder}: {entry.token} [{entry.origin}]")
        console.print()

    return CustomView(
        plain="\n".join(lines),
        object=_mapping_show_object(result),
        rich=rich,
    )


def _set_target_label(result: MappingSetResult) -> str:
    if result.variant is not None:
        return f"{result.group}.variants[{result.variant}].color_mappings.{result.placeholder}"
    return f"{result.group}.color_mappings.{result.placeholder}"


def project_mapping_set_result(result: MappingSetResult) -> CustomView:
    obj = {
        "group": result.group,
        "variant": result.variant,
        "placeholder": result.placeholder,
        "token": result.token,
        "dry_run": result.dry_run,
        "diff": result.diff_text,
    }
    if result.diff_text:
        plain = result.diff_text.rstrip("\n")
        rich_text = result.diff_text
    else:
        confirmation = f"Set {_set_target_label(result)} = {result.token}."
        if result.dry_run:
            confirmation += " (dry run — no changes written)"
        plain = confirmation
        rich_text = confirmation

    def rich(console: Console) -> None:
        console.print()
        console.print(rich_text)
        console.print()

    return CustomView(plain=plain, object=obj, rich=rich)


def project_mapping_set_default_result(result: MappingSetDefaultResult) -> CustomView:
    obj = {
        "placeholder": result.placeholder,
        "token": result.token,
        "dry_run": result.dry_run,
        "diff": result.diff_text,
        "shadows": list(result.shadows),
    }
    if result.shadows:
        shadow_line = f"Shadowing groups: {', '.join(result.shadows)}"
    else:
        shadow_line = "Shadowing groups: none"
    if result.diff_text:
        plain = result.diff_text.rstrip("\n") + "\n" + shadow_line
        rich_text = result.diff_text + "\n" + shadow_line
    else:
        confirmation = f"Set defaults.{result.placeholder} = {result.token}."
        if result.dry_run:
            confirmation += " (dry run — no changes written)"
        plain = confirmation + "\n" + shadow_line
        rich_text = confirmation + "\n" + shadow_line

    def rich(console: Console) -> None:
        console.print()
        console.print(rich_text)
        console.print()

    return CustomView(plain=plain, object=obj, rich=rich)


def _template_analysis_object(result: TemplateAnalysis) -> dict[str, Any]:
    return {
        "path": str(result.path),
        "mode": str(result.mode),
        "shapes": [
            {
                "id": shape.shape_id,
                "tag": shape.tag,
                "paint_attr": shape.paint_attr,
                "placeholder": shape.placeholder,
                "literal": shape.literal,
            }
            for shape in result.shapes
        ],
    }


def project_template_analysis(result: TemplateAnalysis) -> CustomView:
    lines = [f"Template: {result.path}", f"Mode: {result.mode}"]
    lines.append("Shapes:")
    for shape in result.shapes:
        if shape.placeholder is not None:
            value = f"{{{{{shape.placeholder}}}}}"
        elif shape.literal is not None:
            value = shape.literal
        else:
            value = "(none)"
        lines.append(f"  {shape.shape_id}  {shape.tag}  {shape.paint_attr}={value}")

    def rich(console: Console) -> None:
        console.print()
        console.print(Text(f"Template: {result.path}", style="bold"))
        console.print(f"Mode: {result.mode}")
        for shape in result.shapes:
            if shape.placeholder is not None:
                value = f"{{{{{shape.placeholder}}}}}"
            elif shape.literal is not None:
                value = shape.literal
            else:
                value = "(none)"
            console.print(f"  {shape.shape_id}  {shape.tag}  {shape.paint_attr}={value}")
        console.print()

    return CustomView(
        plain="\n".join(lines),
        object=_template_analysis_object(result),
        rich=rich,
    )


def project_message(msg: str) -> MessageView:
    return MessageView(text=msg)


def project_error(exc: IconRendererError) -> ErrorView:
    return ErrorView(kind=type(exc).__name__, message=str(exc), details={})
