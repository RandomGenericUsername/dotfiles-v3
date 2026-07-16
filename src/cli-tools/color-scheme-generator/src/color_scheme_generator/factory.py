from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from color_scheme_generator.adapters.backends.custom_generator import CustomGenerator
from color_scheme_generator.adapters.backends.pywal_generator import PywalGenerator
from color_scheme_generator.adapters.backends.wallust_generator import WallustGenerator
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.ports.output import OutputPort
from color_scheme_generator.ports.palette_generator import PaletteGeneratorPort

if TYPE_CHECKING:
    from color_scheme_generator.adapters.local_processor import LocalProcessor

BackendRegistry = dict[Backend, PaletteGeneratorPort]


@dataclass
class CliDependencies:
    backend_registry: BackendRegistry
    output_adapter: OutputPort | None = None
    processor: LocalProcessor | None = None


def create_backend_registry() -> BackendRegistry:
    return {
        Backend.CUSTOM: CustomGenerator(),
        Backend.PYWAL: PywalGenerator(),
        Backend.WALLUST: WallustGenerator(),
    }
