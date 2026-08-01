from __future__ import annotations

from typing import Any

from cli_output.domain.views import CustomView, ErrorView, MessageView
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from color_scheme_generator.domain.exceptions import (
    BackendNotAvailableError,
    ColorExtractionError,
    ColorSchemeError,
    ConfigResolutionError,
    InvalidImageError,
    OutputWriteError,
    PaletteGenerationError,
    TemplateNotFoundError,
    TemplateRenderError,
)
from color_scheme_generator.domain.models import Color, ColorScheme, GenerationResult


def _color_to_dict(color: Color) -> dict:
    return {"hex": color.hex, "rgb": list(color.rgb)}


def _serialize_color_scheme(scheme: ColorScheme | None) -> dict:
    if scheme is None:
        return {}
    return {
        "background": _color_to_dict(scheme.background),
        "foreground": _color_to_dict(scheme.foreground),
        "cursor": _color_to_dict(scheme.cursor),
        "colors": [_color_to_dict(c) for c in scheme.colors],
        "source_image": str(scheme.source_image),
        "backend": scheme.backend.value,
        "generated_at": scheme.generated_at.isoformat(),
    }


def _serialize_settings(settings: object) -> dict:
    from dataclasses import fields

    result: dict[str, Any] = {}
    for f in fields(settings):
        val = getattr(settings, f.name)
        if hasattr(val, "__dataclass_fields__"):
            result[f.name] = _serialize_settings(val)
        elif isinstance(val, tuple):
            result[f.name] = [
                _serialize_settings(v) if hasattr(v, "__dataclass_fields__") else str(v)
                for v in val
            ]
        elif isinstance(val, dict):
            if val and hasattr(next(iter(val.values())), "__dataclass_fields__"):
                result[f.name] = {k: _serialize_settings(v) for k, v in val.items()}
            else:
                result[f.name] = {k: str(v) for k, v in val.items()}
        else:
            result[f.name] = val.value if hasattr(val, "value") else str(val)
    return result


def project_result(result: GenerationResult) -> CustomView:
    obj: dict[str, Any] = {
        "success": result.success,
        "color_scheme": _serialize_color_scheme(result.color_scheme),
        "output_files": [str(p) for p in result.output_files],
        "backend": result.backend.value,
        "duration": result.duration,
        "command": result.command or None,
    }
    lines = ["Success"]
    lines.append(f"Backend: {result.backend.value}")
    lines.append(f"Duration: {result.duration:.2f}s")
    if result.output_files:
        lines.append("Output files:")
        for path in result.output_files:
            lines.append(f"  {path}")
    lines.append("")

    def rich(console: Console) -> None:
        console.print()
        console.print(
            Text(
                "Success" if result.success else "Failure",
                style="bold green" if result.success else "bold red",
            )
        )
        console.print()
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        table.add_row("Backend", result.backend.value)
        table.add_row("Duration", f"{result.duration:.2f}s")
        if result.color_scheme:
            table.add_row("Background", result.color_scheme.background.hex)
            table.add_row("Foreground", result.color_scheme.foreground.hex)
            table.add_row("Cursor", result.color_scheme.cursor.hex)
        console.print(table)
        console.print()
        if result.output_files:
            console.print(Text("Output files:", style="bold"))
            for path in result.output_files:
                console.print(f"  {path}")
        console.print()

    return CustomView(plain="\n".join(lines), object=obj, rich=rich)


def _error_details(exc: ColorSchemeError) -> dict[str, str]:
    details: dict[str, str] = {}
    if isinstance(exc, InvalidImageError):
        details["image_path"] = str(exc.image_path)
        details["reason"] = exc.reason
    elif isinstance(exc, ColorExtractionError):
        details["backend"] = exc.backend.value
        details["stderr"] = exc.stderr
    elif isinstance(exc, BackendNotAvailableError):
        details["backend"] = exc.backend.value
        details["hint"] = exc.hint
    elif isinstance(exc, OutputWriteError):
        details["path"] = str(exc.path)
        details["reason"] = exc.reason
    elif isinstance(exc, ConfigResolutionError):
        details["key"] = exc.key
        details["reason"] = exc.reason
        if exc.source is not None:
            details["source"] = str(exc.source)
    elif isinstance(exc, PaletteGenerationError):
        if exc.backend is not None:
            details["backend"] = exc.backend.value
    elif isinstance(exc, TemplateNotFoundError):
        details["template"] = exc.template_name
        details["searched"] = ", ".join(str(p) for p in exc.searched_paths)
    elif isinstance(exc, TemplateRenderError):
        details["template"] = exc.template_name
        details["reason"] = exc.reason
    return details


def project_error(exc: ColorSchemeError) -> ErrorView:
    return ErrorView(kind=type(exc).__name__, message=str(exc), details=_error_details(exc))


def project_message(msg: str) -> MessageView:
    return MessageView(text=msg)


def project_palette(scheme: ColorScheme) -> CustomView:
    obj = _serialize_color_scheme(scheme)
    plain = "\n".join(
        [
            f"Background: {scheme.background.hex}",
            f"Foreground: {scheme.foreground.hex}",
            f"Cursor: {scheme.cursor.hex}",
            f"Colors: {' '.join(c.hex for c in scheme.colors)}",
            "",
        ]
    )

    def rich(console: Console) -> None:
        console.print()
        console.print(Text("Palette Display", style="bold"))
        console.print(
            f"[on #{scheme.foreground.hex[1:]}]{' ' * 20}[/] Foreground: {scheme.foreground.hex}"
        )
        console.print(f"[on #{scheme.cursor.hex[1:]}]{' ' * 20}[/] Cursor: {scheme.cursor.hex}")
        console.print()
        for i in range(0, len(scheme.colors), 8):
            row_colors = scheme.colors[i : i + 8]
            line = "".join(f"[on #{c.hex[1:]}]{' ' * 10}[/] " for c in row_colors)
            console.print(line)
            labels = "  ".join(f"{c.hex:<12}" for c in row_colors)
            console.print(labels)
            console.print()
        console.print()

    return CustomView(plain=plain, object=obj, rich=rich)


def _settings_sections(settings: object) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if not settings:
        return rows
    for section, _fields in settings.__dataclass_fields__.items():
        section_val = getattr(settings, section)
        if hasattr(section_val, "__dataclass_fields__"):
            for field in section_val.__dataclass_fields__:
                val = getattr(section_val, field)
                rows.append((f"{section}.{field}", str(val)))
    return rows


def project_config_info(
    settings: object,
    backends: dict,
    sources: list[str],
    templates: object = None,
) -> CustomView:
    obj: dict[str, Any] = {
        "settings": _serialize_settings(settings) if settings else {},
        "backends": backends,
        "templates": (
            {
                "templates_count": len(templates.templates),  # type: ignore[union-attr]
                "formats": [t.format.value for t in templates.templates],  # type: ignore[union-attr]
            }
            if templates
            else {"templates_count": 0, "formats": []}
        ),
        "sources": sources,
    }

    lines: list[str] = []
    for section, value in _settings_sections(settings):
        lines.append(f"{section}: {value}")
    lines.append("")
    if sources:
        lines.append("Sources:")
        for s in sources:
            lines.append(f"  {s}")
    lines.append("")
    lines.append("Templates:")
    if templates and templates.templates:  # type: ignore[union-attr]
        lines.append(f"  count: {len(templates.templates)}")  # type: ignore[union-attr]
        lines.append(f"  formats: {', '.join(t.format.value for t in templates.templates)}")  # type: ignore[union-attr]
    else:
        lines.append("  count: 0")
    lines.append("")
    lines.append("Backends:")
    for name, info in backends.items():
        avail = "available" if info.get("available") else "not available"
        desc = info.get("description", "")
        lines.append(f"  {name}: {avail}")
        if desc:
            lines.append(f"    description: {desc}")

    def rich(console: Console) -> None:
        table = Table(title="Configuration", box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        for section, value in _settings_sections(settings):
            table.add_row(section, value)
        console.print()
        console.print(table)
        console.print()
        if sources:
            src_table = Table(title="Sources", box=None)
            src_table.add_column("Source")
            for s in sources:
                src_table.add_row(s)
            console.print(src_table)
            console.print()
        tpl_table = Table(title="Templates", box=None)
        tpl_table.add_column("Format", style="cyan")
        tpl_table.add_column("File")
        if templates and templates.templates:  # type: ignore[union-attr]
            for t in templates.templates:  # type: ignore[union-attr]
                tpl_table.add_row(t.format.value, t.name)
        else:
            tpl_table.add_row("(none)", "")
        console.print(tpl_table)
        console.print()
        bk_table = Table(title="Backends", box=None)
        bk_table.add_column("Backend", style="cyan")
        bk_table.add_column("Available")
        for name, info in backends.items():
            bk_table.add_row(name, "yes" if info.get("available") else "no")
        console.print(bk_table)
        console.print()

    return CustomView(plain="\n".join(lines), object=obj, rich=rich)


def _project_install_like(title: str, results: list[dict]) -> CustomView:
    obj: dict[str, Any] = {title: results}
    lines = [f"{r['backend']}: {r['image']} [{r['status']}]" for r in results]

    def rich(console: Console) -> None:
        table = Table(title=f"{title.title()} Results", box=None)
        table.add_column("Backend", style="cyan")
        table.add_column("Image")
        table.add_column("Status")
        for r in results:
            table.add_row(r["backend"], r["image"], r["status"])
        console.print()
        console.print(table)
        console.print()

    return CustomView(plain="\n".join(lines), object=obj, rich=rich)


def project_install(results: list[dict]) -> CustomView:
    return _project_install_like("install", results)


def project_uninstall(results: list[dict]) -> CustomView:
    return _project_install_like("uninstall", results)


def project_version(version: str) -> CustomView:
    return CustomView(
        plain=f"color-scheme-generator {version}",
        object={"version": version},
        rich=f"[bold]color-scheme-generator[/bold] v{version}",
    )


def project_backends(backends: list[dict], hint: str = "") -> CustomView:
    obj: dict[str, Any] = {"backends": backends}
    if hint:
        obj["hint"] = hint

    lines: list[str] = []
    for b in backends:
        desc = b.get("description", "")
        avail = "yes" if b["available"] else "no"
        lines.append(f"{b['name']} - {desc}")
        lines.append(f"  Available: {avail}")
        lines.append("  Image: not implemented")
        if b.get("parameters"):
            lines.append("  Parameters:")
            for p in b["parameters"]:
                choices = f", choices: {', '.join(p['choices'])}" if p.get("choices") else ""
                lines.append(
                    f"    {p['name']} ({p['type']}, default: {p.get('default', '')}{choices})"
                )
    if hint:
        lines.append("")
        lines.append(f"Tip: {hint}")

    def rich(console: Console) -> None:
        for b in backends:
            table = Table(title=b.get("display_name", b["name"]), box=None)
            table.add_column("Property", style="cyan")
            table.add_column("Value")
            table.add_row("Name", b["name"])
            table.add_row("Description", b.get("description", ""))
            table.add_row("Available", "yes" if b["available"] else "no")
            img = "not implemented" if b["image_available"] is None else str(b["image_available"])
            table.add_row("Image", img)
            if b.get("parameters"):
                params_table = Table(title="Parameters", box=None)
                params_table.add_column("Name", style="cyan")
                params_table.add_column("Type")
                params_table.add_column("Default")
                params_table.add_column("Choices")
                for p in b["parameters"]:
                    choices = ", ".join(p["choices"]) if p.get("choices") else ""
                    default = p.get("default", "")
                    params_table.add_row(p["name"], p["type"], str(default), choices)
                console.print(params_table)
                console.print()
            console.print(table)
            console.print()
        if hint:
            console.print(Panel(hint, title="Tip", border_style="yellow"))
            console.print()

    return CustomView(plain="\n".join(lines), object=obj, rich=rich)
