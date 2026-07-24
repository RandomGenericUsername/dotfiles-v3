from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError, TemplateNotFound

from color_scheme_generator.domain.exceptions import TemplateNotFoundError, TemplateRenderError
from color_scheme_generator.domain.models import ColorScheme
from color_scheme_generator.ports.template_dir_resolver import TemplateDirResolverPort


class JinjaTemplateRenderer:
    def __init__(self, resolver: TemplateDirResolverPort) -> None:
        self._resolver = resolver
        self._init_env()

    def _init_env(self, settings_dir: Path | None = None) -> None:
        templates_dir = self._resolver.resolve(settings_dir=settings_dir)
        self._templates_dir = templates_dir
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def update_templates_dir(self, settings_dir: Path | None) -> None:
        self._init_env(settings_dir=settings_dir)

    def render(self, template_name: str, scheme: ColorScheme, output_path: Path) -> None:
        if not template_name:
            raise ValueError("template_name must be non-empty")
        if os.path.basename(template_name) != template_name:
            raise ValueError(f"Invalid template_name: {template_name}")
        if not isinstance(scheme, ColorScheme):
            raise TypeError(f"Expected ColorScheme, got {type(scheme).__name__}")
        if not isinstance(output_path, Path):
            output_path = Path(output_path)

        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound:
            if self._templates_dir.is_dir():
                searched = tuple(self._templates_dir.iterdir())
            else:
                searched = (self._templates_dir,)
            raise TemplateNotFoundError(template_name, searched) from None
        except TemplateError as exc:
            raise TemplateRenderError(template_name, f"Template compilation failed: {exc}") from exc

        colors_list = list(scheme.colors)

        context = {
            "source_image": str(scheme.source_image),
            "backend": scheme.backend.value,
            "generated_at": scheme.generated_at.isoformat(),
            "background": scheme.background,
            "foreground": scheme.foreground,
            "cursor": scheme.cursor,
            "colors": colors_list,
        }

        try:
            rendered = template.render(**context)
        except TemplateError as exc:
            raise TemplateRenderError(template_name, str(exc)) from exc

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        except OSError as exc:
            msg = f"Failed to create output directory: {exc}"
            raise TemplateRenderError(template_name, msg) from exc

        if template_name.endswith("sequences.j2"):
            rendered = rendered.replace("]", "\x1b]").replace("\\", "\x1b\\")
            self._write_output(output_path, rendered.encode("utf-8"))
        else:
            self._write_output(output_path, rendered)

    def _write_output(self, path: Path, data: str | bytes) -> None:
        try:
            if isinstance(data, bytes):
                path.write_bytes(data)
            else:
                path.write_text(data, encoding="utf-8")
        except OSError as exc:
            msg = f"Failed to write output: {exc}"
            raise TemplateRenderError(str(path.name), msg) from exc
