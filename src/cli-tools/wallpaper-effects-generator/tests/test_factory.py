from __future__ import annotations

from pathlib import Path

from wallpaper_effects_generator.adapters.assembled_config_resolver import (
    AssembledConfigResolver,
)
from wallpaper_effects_generator.adapters.dry_run_processor import DryRunProcessor
from wallpaper_effects_generator.adapters.importlib_version_provider import (
    ImportlibVersionProvider,
)
from wallpaper_effects_generator.adapters.local_processor import LocalProcessor
from wallpaper_effects_generator.adapters.output.json_output import JsonOutputAdapter
from wallpaper_effects_generator.adapters.output.plain_output import PlainOutputAdapter
from wallpaper_effects_generator.adapters.output.rich_output import RichOutputAdapter
from wallpaper_effects_generator.adapters.subprocess_runner import (
    SubprocessCommandRunner,
)
from wallpaper_effects_generator.adapters.yaml_effect_loader import YamlEffectLoader
from wallpaper_effects_generator.domain.enums import OutputFormat
from wallpaper_effects_generator.domain.models import EffectsCatalog
from wallpaper_effects_generator.factory import (
    create_command_runner,
    create_config_resolver,
    create_dry_run_processor,
    create_effect_loader,
    create_local_processor,
    create_output_adapter,
    create_version_provider,
)
from wallpaper_effects_generator.ports.command_runner import CommandRunnerPort
from wallpaper_effects_generator.ports.config_resolver import ConfigResolverPort
from wallpaper_effects_generator.ports.effect_loader import EffectLoaderPort
from wallpaper_effects_generator.ports.output import OutputPort
from wallpaper_effects_generator.ports.processor import EffectProcessorPort
from wallpaper_effects_generator.ports.version_provider import VersionProviderPort


def test_create_config_resolver_returns_port():
    resolver = create_config_resolver()
    assert isinstance(resolver, ConfigResolverPort)
    assert isinstance(resolver, AssembledConfigResolver)


def test_create_effect_loader_returns_port():
    loader = create_effect_loader()
    assert isinstance(loader, EffectLoaderPort)
    assert isinstance(loader, YamlEffectLoader)


def test_create_command_runner_returns_subprocess():
    from wallpaper_effects_generator.domain.models import (
        AppSettings,
        BackendSettings,
    )

    settings = AppSettings(backend=BackendSettings(binary="magick"))
    runner = create_command_runner(settings=settings)
    assert isinstance(runner, CommandRunnerPort)
    assert isinstance(runner, SubprocessCommandRunner)


def test_create_local_processor_with_deps():
    from unittest.mock import Mock

    mock_runner = Mock()
    processor = create_local_processor(
        command_runner=mock_runner,
        catalog=EffectsCatalog(),
        output_dir=Path("/tmp"),
    )
    assert isinstance(processor, EffectProcessorPort)
    assert isinstance(processor, LocalProcessor)


def test_create_dry_run_processor_with_deps():
    from unittest.mock import Mock

    mock_runner = Mock()
    processor = create_dry_run_processor(
        command_runner=mock_runner,
        catalog=EffectsCatalog(),
        output_dir=Path("/tmp"),
    )
    assert isinstance(processor, EffectProcessorPort)
    assert isinstance(processor, DryRunProcessor)


def test_create_output_adapter_json_returns_port():
    adapter = create_output_adapter(OutputFormat.JSON)
    assert isinstance(adapter, OutputPort)
    assert isinstance(adapter, JsonOutputAdapter)


def test_create_output_adapter_rich_returns_port():
    adapter = create_output_adapter(OutputFormat.RICH)
    assert isinstance(adapter, OutputPort)
    assert isinstance(adapter, RichOutputAdapter)


def test_create_output_adapter_plain_returns_port():
    adapter = create_output_adapter(OutputFormat.PLAIN)
    assert isinstance(adapter, OutputPort)
    assert isinstance(adapter, PlainOutputAdapter)


def test_create_version_provider_returns_port():
    provider = create_version_provider()
    assert isinstance(provider, VersionProviderPort)
    assert isinstance(provider, ImportlibVersionProvider)
