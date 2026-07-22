from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from color_scheme_generator.domain.models import (
        AppSettings,
        GenerationRequest,
        GenerationResult,
    )


class DryRunProcessor:
    def __init__(
        self,
    ) -> None:
        pass

    def process_generate(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        raise NotImplementedError("DryRunProcessor will be implemented in story 4.1")

    def process_show(
        self, request: GenerationRequest, settings: AppSettings
    ) -> GenerationResult:
        raise NotImplementedError("DryRunProcessor will be implemented in story 4.1")
