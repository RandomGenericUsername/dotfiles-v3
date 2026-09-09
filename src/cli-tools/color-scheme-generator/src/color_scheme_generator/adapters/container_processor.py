from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from oci_runtime import engine_qualified_image

from color_scheme_generator.domain.enums import Backend, ColorFormat
from color_scheme_generator.domain.exceptions import (
    ContainerImageNotFoundError,
    ContainerTimeoutError,
    InvalidImageError,
)
from color_scheme_generator.domain.models import (
    Color,
    ColorScheme,
    ContainerMount,
    GenerationResult,
)

logger = logging.getLogger(__name__)

_CONTAINER_ENV = {
    "HOME": "/tmp",
    "XDG_CONFIG_HOME": "/tmp/.config",
    "XDG_CACHE_HOME": "/tmp/.cache",
    "COLORSCHEME_CONFIG_FILE_PATH": "/csg-config/settings.toml",
    "COLORSCHEME_TEMPLATES_TEMPLATES_DIR": "/templates",
    "COLORSCHEME__RUNTIME__MODE": "local",
}

if TYPE_CHECKING:
    from color_scheme_generator.adapters.template_dir_resolver import TemplateDirResolver
    from color_scheme_generator.domain.models import (
        AppSettings,
        GenerationRequest,
    )
    from color_scheme_generator.ports.container_runtime import ContainerRuntimePort


class ContainerProcessor:
    def __init__(
        self,
        container_runtime: ContainerRuntimePort,
        template_dir_resolver: TemplateDirResolver | None = None,
        default_settings_path: Path | None = None,
        engine_value: str | None = None,
        templates_dir: Path | str | None = None,
    ) -> None:
        self._container_runtime = container_runtime
        self._template_dir_resolver = template_dir_resolver
        self._default_settings_path = default_settings_path
        self._engine_value = engine_value
        # Explicit CLI --templates-dir (main.py): wins over every resolver
        # chain branch below, so the container bind-mounts the SAME dir the
        # local processor would render from. Without it, container mode
        # silently ignored the flag and mounted resolver defaults instead.
        self._templates_dir = Path(templates_dir) if templates_dir is not None else None

    def _select_image(self, settings: AppSettings, backend_value: str) -> str:
        prefix = settings.container.image_prefix
        tag = settings.container.image_tag
        engine = self._engine_value or settings.container.engine
        base = f"{prefix}-{backend_value}"
        return engine_qualified_image(base, engine, tag)

    def _serialize_settings(self, settings: AppSettings) -> str:
        lines: list[str] = []
        def kv(key: str, value: object) -> None:
            if value is None:
                lines.append(f"# {key} = null")
            elif isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            elif isinstance(value, (int, float)):
                lines.append(f"{key} = {value}")
            else:
                escaped = str(value).replace("\\", "\\\\").replace("\"", "\\\"")
                lines.append(f"{key} = \"{escaped}\"")

        lines.append("[output]")
        kv("directory", str(settings.output.directory))
        fmt_list = ", ".join(
            f'"{f.value}"' if isinstance(f, ColorFormat) else f'"{f}"'
            for f in settings.output.default_formats
        )
        lines.append(f"default_formats = [{fmt_list}]")
        kv("overwrite", settings.output.overwrite)
        kv("apply_to_terminal", settings.output.apply_to_terminal)
        lines.append("")
        lines.append("[generation]")
        kv("backend", settings.generation.backend.value)
        if settings.generation.default_params:
            lines.append("default_params = {")
            for k, v in settings.generation.default_params.items():
                ev = str(v).replace("\\", "\\\\").replace("\"", "\\\"")
                lines.append(f"  \"{k}\" = \"{ev}\",")
            lines.append("}")
        lines.append("")
        lines.append("[runtime]")
        kv("mode", settings.runtime.mode.value)
        lines.append("")
        lines.append("[container]")
        kv("engine", settings.container.engine)
        kv("image_prefix", settings.container.image_prefix)
        kv("image_tag", settings.container.image_tag)
        kv("timeout_seconds", settings.container.timeout_seconds)
        kv("memory_limit", settings.container.memory_limit)
        kv("mount_timeout_seconds", settings.container.mount_timeout_seconds)
        return "\n".join(lines) + "\n"

    def _parse_color_scheme_from_json(self, raw: str) -> ColorScheme | None:
        if not raw.strip():
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        try:
            return ColorScheme(
                background=Color(data["background"]["hex"], tuple(data["background"]["rgb"])),
                foreground=Color(data["foreground"]["hex"], tuple(data["foreground"]["rgb"])),
                cursor=Color(data["cursor"]["hex"], tuple(data["cursor"]["rgb"])),
                colors=tuple(
                    Color(c["hex"], tuple(c["rgb"])) for c in data["colors"]
                ),
                source_image=Path(data["source_image"]),
                backend=Backend(data["backend"]),
                generated_at=datetime.fromisoformat(data["generated_at"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _resolve_templates_dir(self) -> Path:
        """Templates dir for the /templates bind-mount.

        Precedence: explicit CLI ``--templates-dir`` > resolver chain >
        settings-adjacent defaults > system path. The explicit branch is
        what makes ``csg generate --templates-dir <dir> --runtime
        container`` mount the requested dir instead of silently mounting
        resolver defaults (the container previously ignored the flag).
        """
        if self._templates_dir is not None:
            templates_dir = self._templates_dir
        elif self._template_dir_resolver:
            templates_dir = self._template_dir_resolver.resolve()
        elif self._default_settings_path:
            templates_dir = (
                self._default_settings_path.parent / "defaults" / "templates"
            )
        else:
            templates_dir = Path(
                "/usr/share/color-scheme-generator/templates"
            )
        if not templates_dir.is_dir():
            raise FileNotFoundError(f"Templates directory not found: {templates_dir}")
        return templates_dir

    def process_generate(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        start = time.monotonic()
        temp_toml_path: Path | None = None

        try:
            image = self._select_image(settings, request.config.backend.value)

            if not self._container_runtime.image_exists(image):
                raise ContainerImageNotFoundError(image, request.config.backend)

            input_parent = request.image_path.resolve().parent
            if input_parent == Path("/"):
                raise InvalidImageError(
                    request.image_path,
                    "Cannot mount filesystem root as input directory",
                )

            if not request.image_path.is_file():
                raise FileNotFoundError(f"Input image not found: {request.image_path}")

            output_dir = request.config.output_dir
            output_dir.mkdir(parents=True, exist_ok=True)

            templates_dir = self._resolve_templates_dir()

            toml_content = self._serialize_settings(settings)
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".toml", mode="w"
            ) as f:
                f.write(toml_content)
                temp_toml_path = Path(f.name)

            try:
                os.chmod(temp_toml_path, 0o644)
            except OSError:
                logger.warning("Failed to chmod temp config file: %s", temp_toml_path)

            mounts = [
                ContainerMount(
                    source=input_parent,
                    target=PurePosixPath("/input"),
                    read_only=True,
                ),
                ContainerMount(
                    source=output_dir,
                    target=PurePosixPath("/output"),
                    read_only=False,
                ),
                ContainerMount(
                    source=temp_toml_path,
                    target=PurePosixPath("/csg-config/settings.toml"),
                    read_only=True,
                ),
                ContainerMount(
                    source=templates_dir,
                    target=PurePosixPath("/templates"),
                    read_only=True,
                ),
            ]

            inner_command = [
                "csg",
                "generate",
                f"/input/{request.image_path.name}",
                "--backend",
                request.config.backend.value,
            ]
            for key, value in request.config.params.items():
                inner_command.extend(["--param", f"{key}={value}"])
            for fmt in request.config.formats:
                inner_command.extend(["--format", fmt.value])
            inner_command.extend(["-o", "/output"])
            command_str = " ".join(inner_command)

            try:
                container_result = self._container_runtime.run(
                    image=image,
                    command=inner_command,
                    mounts=mounts,
                    timeout=settings.container.timeout_seconds,
                    environment=_CONTAINER_ENV,
                )
            except ContainerTimeoutError:
                raise
            except Exception as exc:
                from color_scheme_generator.adapters.error_mapping import map_oci_error

                raise map_oci_error(exc, backend=request.config.backend) from exc

            duration = time.monotonic() - start

            inner = {}
            if container_result.return_code == 0 and container_result.stdout:
                try:
                    inner = json.loads(container_result.stdout)
                except json.JSONDecodeError:
                    pass

            cs_data = inner.get("color_scheme")
            if cs_data and isinstance(cs_data, dict):
                from color_scheme_generator.domain.models import Color as _Color
                color_scheme = ColorScheme(
                    background=_Color(cs_data["background"]["hex"], tuple(cs_data["background"]["rgb"])),
                    foreground=_Color(cs_data["foreground"]["hex"], tuple(cs_data["foreground"]["rgb"])),
                    cursor=_Color(cs_data["cursor"]["hex"], tuple(cs_data["cursor"]["rgb"])),
                    colors=tuple(_Color(c["hex"], tuple(c["rgb"])) for c in cs_data["colors"]),
                    source_image=request.image_path.resolve(),
                    backend=Backend(cs_data["backend"]),
                    generated_at=datetime.fromisoformat(cs_data["generated_at"]),
                )
            else:
                color_scheme = None

            container_output = Path("/output")
            host_output = request.config.output_dir
            inner_files = inner.get("output_files", [])
            if inner_files:
                output_files = tuple(
                    Path(str(p).replace(str(container_output), str(host_output)))
                    for p in inner_files
                )
            else:
                output_files = (
                    tuple(output_dir.iterdir()) if output_dir.exists() else ()
                )

            return GenerationResult(
                success=container_result.return_code == 0,
                color_scheme=color_scheme,
                output_files=output_files,
                backend=request.config.backend,
                stderr=container_result.stderr,
                return_code=container_result.return_code,
                duration=duration,
                command=command_str,
            )

        except ContainerTimeoutError:
            return GenerationResult(
                success=False,
                color_scheme=None,
                output_files=(),
                backend=request.config.backend,
                stderr="Container execution timed out",
                return_code=-1,
                duration=time.monotonic() - start,
            )
        finally:
            if temp_toml_path is not None and temp_toml_path.exists():
                temp_toml_path.unlink()

    def process_show(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        start = time.monotonic()
        temp_toml_path: Path | None = None

        try:
            image = self._select_image(settings, request.config.backend.value)

            if not self._container_runtime.image_exists(image):
                raise ContainerImageNotFoundError(image, request.config.backend)

            input_parent = request.image_path.resolve().parent
            if input_parent == Path("/"):
                raise InvalidImageError(
                    request.image_path,
                    "Cannot mount filesystem root as input directory",
                )

            if not request.image_path.is_file():
                raise FileNotFoundError(f"Input image not found: {request.image_path}")

            templates_dir = self._resolve_templates_dir()

            toml_content = self._serialize_settings(settings)
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".toml", mode="w"
            ) as f:
                f.write(toml_content)
                temp_toml_path = Path(f.name)

            try:
                os.chmod(temp_toml_path, 0o644)
            except OSError:
                logger.warning("Failed to chmod temp config file: %s", temp_toml_path)

            mounts = [
                ContainerMount(
                    source=input_parent,
                    target=PurePosixPath("/input"),
                    read_only=True,
                ),
                ContainerMount(
                    source=temp_toml_path,
                    target=PurePosixPath("/csg-config/settings.toml"),
                    read_only=True,
                ),
                ContainerMount(
                    source=templates_dir,
                    target=PurePosixPath("/templates"),
                    read_only=True,
                ),
            ]

            inner_command = [
                "csg",
                "show",
                f"/input/{request.image_path.name}",
                "--backend",
                request.config.backend.value,
            ]
            for key, value in request.config.params.items():
                inner_command.extend(["--param", f"{key}={value}"])
            command_str = " ".join(inner_command)

            try:
                container_result = self._container_runtime.run(
                    image=image,
                    command=inner_command,
                    mounts=mounts,
                    timeout=settings.container.timeout_seconds,
                    environment=_CONTAINER_ENV,
                )
            except ContainerTimeoutError:
                raise
            except Exception as exc:
                from color_scheme_generator.adapters.error_mapping import map_oci_error

                raise map_oci_error(exc, backend=request.config.backend) from exc

            duration = time.monotonic() - start

            color_scheme = self._parse_color_scheme_from_json(container_result.stdout)
            if color_scheme is not None:
                from dataclasses import replace
                color_scheme = replace(color_scheme, source_image=request.image_path.resolve())

            return GenerationResult(
                success=container_result.return_code == 0,
                color_scheme=color_scheme,
                output_files=(),
                backend=request.config.backend,
                stderr=container_result.stderr,
                return_code=container_result.return_code,
                duration=duration,
                command=command_str,
            )

        except ContainerTimeoutError:
            return GenerationResult(
                success=False,
                color_scheme=None,
                output_files=(),
                backend=request.config.backend,
                stderr="Container execution timed out",
                return_code=-1,
                duration=time.monotonic() - start,
            )
        finally:
            if temp_toml_path is not None and temp_toml_path.exists():
                temp_toml_path.unlink()
