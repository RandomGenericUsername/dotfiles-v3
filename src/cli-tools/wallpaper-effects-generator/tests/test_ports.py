from __future__ import annotations

from pathlib import Path
from typing import Protocol

from wallpaper_effects_generator.ports.command_runner import CommandRunnerPort
from wallpaper_effects_generator.ports.config_resolver import ConfigResolverPort
from wallpaper_effects_generator.ports.context_validator import ContextValidatorPort
from wallpaper_effects_generator.ports.effect_loader import EffectLoaderPort
from wallpaper_effects_generator.ports.output import OutputPort
from wallpaper_effects_generator.ports.processor import EffectProcessorPort
from wallpaper_effects_generator.ports.serializers import (
    EffectsSerializerPort,
    SettingsSerializerPort,
)
from wallpaper_effects_generator.ports.version_provider import VersionProviderPort


def _verify_protocol(cls: type[Protocol], obj: object) -> bool:
    return isinstance(obj, cls)


class TestPortProtocols:
    def test_effect_loader_protocol(self) -> None:
        class StubLoader:
            def load(self, path: Path | None = None) -> object:
                return object()

            def get_default_path(self) -> Path:
                return Path("/default")

            def get_resolved_path(self) -> Path | None:
                return None

        assert _verify_protocol(EffectLoaderPort, StubLoader())

    def test_config_resolver_protocol(self) -> None:
        class StubResolver:
            def resolve(
                self,
                explicit_path: Path | None = None,
                cli_overrides: dict[str, str] | None = None,
            ) -> object:
                return object()

            def get_resolved_path(self) -> Path | None:
                return None

        assert _verify_protocol(ConfigResolverPort, StubResolver())

    def test_command_runner_protocol(self) -> None:
        class StubRunner:
            def is_available(self, binary: str | None = None) -> bool:
                return True

            def get_binary(self) -> str:
                return "magick"

            def execute(self, command: str | list[str], timeout: int | None = None) -> object:
                return object()

        assert _verify_protocol(CommandRunnerPort, StubRunner())

    def test_effect_processor_protocol(self) -> None:
        class StubProcessor:
            def process_effect(
                self, name: str, request: object, params: dict | None = None
            ) -> object:
                return object()

            def process_composite(
                self, name: str, request: object, params: dict | None = None
            ) -> object:
                return object()

            def process_preset(
                self, name: str, request: object, params: dict | None = None
            ) -> object:
                return object()

            def process_batch(self, request: object) -> object:
                return object()

        assert _verify_protocol(EffectProcessorPort, StubProcessor())

    def test_output_protocol(self) -> None:
        class StubOutput:
            def process_result(self, result: object) -> None:
                pass

            def batch_result(self, result: object) -> None:
                pass

            def catalog_list(self, catalog: object, query: object) -> None:
                pass

            def config_info(self, settings: object, catalog: object, sources: list[str]) -> None:
                pass

            def dump_config_template(self, content: str) -> None:
                pass

            def dump_effects_template(self, content: str) -> None:
                pass

            def error(self, exc: Exception) -> None:
                pass

            def message(self, msg: str) -> None:
                pass

        assert _verify_protocol(OutputPort, StubOutput())

    def test_settings_serializer_protocol(self) -> None:
        class StubSerializer:
            def serialize(self, settings: object, path: Path) -> None:
                pass

            def deserialize(self, path: Path) -> object:
                return object()

        assert _verify_protocol(SettingsSerializerPort, StubSerializer())

    def test_version_provider_protocol(self) -> None:
        class StubProvider:
            def get_version(self) -> str:
                return "0.0.0"

        assert _verify_protocol(VersionProviderPort, StubProvider())

    def test_effects_serializer_protocol(self) -> None:
        class StubSerializer:
            def serialize(self, catalog: object, path: Path) -> None:
                pass

            def deserialize(self, path: Path) -> object:
                return object()

        assert _verify_protocol(EffectsSerializerPort, StubSerializer())

    def test_context_validator_protocol(self) -> None:
        class StubValidator:
            def validate(
                self,
                input_path: Path | None = None,
                settings: object | None = None,
                catalog: object | None = None,
                output_dir: Path | None = None,
            ) -> object:
                from wallpaper_effects_generator.ports.context_validator import (
                    ContextValidationResult,
                )

                return ContextValidationResult()

        assert _verify_protocol(ContextValidatorPort, StubValidator())
