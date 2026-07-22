from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from color_scheme_generator.adapters.template_dir_resolver import TemplateDirResolver
    from color_scheme_generator.domain.models import (
        AppSettings,
        GenerationRequest,
        GenerationResult,
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

    def process_generate(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        raise NotImplementedError("ContainerProcessor will be implemented in story 3.2")

    def process_show(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        raise NotImplementedError("ContainerProcessor will be implemented in story 3.2")
