from __future__ import annotations

import logging
import shutil
from importlib.resources import files as resource_files
from pathlib import Path

import typer

from color_scheme_generator.adapters.template_dir_resolver import TemplateDirResolver
from color_scheme_generator.domain.exceptions import ConfigResolutionError, OutputWriteError
from color_scheme_generator.factory import CliDependencies

logger = logging.getLogger(__name__)

_BUNDLED_TEMPLATES_DIR = "templates"


def dump_templates(
    ctx: typer.Context,
    output: Path | None = typer.Option(None, "--output", "-o", help="Custom target directory"),  # noqa: B008
    overwrite: bool = typer.Option(False, "--overwrite", "-w", help="Overwrite existing files"),  # noqa: B008
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    template_dir_resolver: TemplateDirResolver | None = deps.template_dir_resolver

    if output is not None:
        target_dir = output.resolve()
        if not target_dir.suffix:
            target_dir = target_dir / "templates"
    elif template_dir_resolver is not None:
        try:
            target_dir = template_dir_resolver.resolve()
        except ConfigResolutionError:
            from pathlib import Path
            target_dir = Path.home() / ".config" / "color-scheme" / "templates"
    else:
        from pathlib import Path
        target_dir = Path.home() / ".config" / "color-scheme" / "templates"

    try:
        bundled = resource_files("color_scheme_generator.defaults").joinpath(
            _BUNDLED_TEMPLATES_DIR
        )
    except (ModuleNotFoundError, TypeError) as e:
        msg = f"Failed to find bundled templates: {e}"
        raise ConfigResolutionError(key="templates", reason=msg) from e

    target_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0

    for template_file in sorted(bundled.iterdir()):
        if not template_file.name.endswith(".j2"):
            continue

        target_path = target_dir / template_file.name

        if target_path.exists() and not overwrite:
            logger.info("Skipping existing %s", target_path)
            skipped += 1
            continue

        if target_path.exists() and overwrite:
            if not target_path.parent.stat().st_mode & 0o200:
                msg = f"Target file {target_path} is read-only"
                raise OutputWriteError(path=target_path, reason=msg)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(template_file), str(target_path))
        copied += 1

    adapter = deps.output_adapter
    if adapter is not None:
        adapter.message(f"Copied {copied} template(s) to {target_dir.resolve()}")
