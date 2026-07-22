from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

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
    ) -> None:
        self._container_runtime = container_runtime
        self._template_dir_resolver = template_dir_resolver
        self._default_settings_path = default_settings_path

    def _select_image(self, settings: AppSettings, backend_value: str) -> str:
        prefix = settings.container.image_prefix
        tag = settings.container.image_tag
        return f"{prefix}color-scheme-{backend_value}:{tag}"

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
        fmt_list = ", ".join(f'"{f.value}"' for f in settings.output.default_formats)
        lines.append(f"default_formats = [{fmt_list}]")
        kv("overwrite", settings.output.overwrite)
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
        lines.append("[template]")
        tdir = settings.template.templates_dir
        kv("templates_dir", str(tdir) if tdir else None)
        cdir = settings.template.custom_templates_dir
        kv("custom_templates_dir", str(cdir) if cdir else None)
        lines.append("")
        lines.append("[runtime]")
        kv("mode", settings.runtime.mode.value)
        kv("engine", settings.runtime.engine.value)
        lines.append("")
        lines.append("[container]")
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
                backend=data["backend"],
                generated_at=data["generated_at"],
            )
        except (KeyError, TypeError, ValueError):
            return None

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

            if self._template_dir_resolver:
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
                "--runtime",
                "local",
                "--backend",
                request.config.backend.value,
            ]
            for key, value in request.config.params.items():
                inner_command.extend(["--param", f"{key}={value}"])
            for fmt in request.config.formats:
                inner_command.extend(["--format", fmt.value])
            inner_command.extend(["-o", "/output"])

            try:
                container_result = self._container_runtime.run(
                    image=image,
                    command=inner_command,
                    mounts=mounts,
                    timeout=settings.container.timeout_seconds,
                )
            except ContainerTimeoutError:
                raise
            except Exception as exc:
                from color_scheme_generator.adapters.error_mapping import map_oci_error

                raise map_oci_error(exc, backend=request.config.backend) from exc

            duration = time.monotonic() - start

            return GenerationResult(
                success=container_result.return_code == 0,
                color_scheme=None,
                output_files=(
                    tuple(output_dir.iterdir()) if output_dir.exists() else ()
                ),
                backend=request.config.backend,
                stderr=container_result.stderr,
                return_code=container_result.return_code,
                duration=duration,
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

            if self._template_dir_resolver:
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
                "--runtime",
                "local",
                "--backend",
                request.config.backend.value,
            ]
            for key, value in request.config.params.items():
                inner_command.extend(["--param", f"{key}={value}"])

            try:
                container_result = self._container_runtime.run(
                    image=image,
                    command=inner_command,
                    mounts=mounts,
                    timeout=settings.container.timeout_seconds,
                )
            except ContainerTimeoutError:
                raise
            except Exception as exc:
                from color_scheme_generator.adapters.error_mapping import map_oci_error

                raise map_oci_error(exc, backend=request.config.backend) from exc

            duration = time.monotonic() - start

            color_scheme = self._parse_color_scheme_from_json(container_result.stdout)

            return GenerationResult(
                success=container_result.return_code == 0,
                color_scheme=color_scheme,
                output_files=(),
                backend=request.config.backend,
                stderr=container_result.stderr,
                return_code=container_result.return_code,
                duration=duration,
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
