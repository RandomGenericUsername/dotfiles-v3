from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from wallpaper_effects_generator.adapters.assembled_config_resolver import (
    AssembledConfigResolver,
)
from wallpaper_effects_generator.adapters.docker_image_manager import (
    DockerImageManager,
)
from wallpaper_effects_generator.adapters.dry_run_processor import DryRunProcessor
from wallpaper_effects_generator.adapters.importlib_version_provider import (
    ImportlibVersionProvider,
)
from wallpaper_effects_generator.adapters.local_processor import LocalProcessor
from wallpaper_effects_generator.adapters.oci_command_runner import OCICommandRunner
from wallpaper_effects_generator.adapters.output.json_output import JsonOutputAdapter
from wallpaper_effects_generator.adapters.output.plain_output import PlainOutputAdapter
from wallpaper_effects_generator.adapters.output.rich_output import RichOutputAdapter
from wallpaper_effects_generator.adapters.subprocess_runner import (
    SubprocessCommandRunner,
)
from wallpaper_effects_generator.adapters.yaml_effect_loader import YamlEffectLoader
from wallpaper_effects_generator.domain.enums import OutputFormat, RuntimeMode
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BackendSettings,
    ContainerSettings,
    EffectsCatalog,
    RuntimeSettings,
)
from wallpaper_effects_generator.factory import (
    create_command_runner,
    create_config_resolver,
    create_container_processor,
    create_dry_run_processor,
    create_effect_loader,
    create_image_manager,
    create_local_processor,
    create_oci_command_runner,
    create_output_adapter,
    create_version_provider,
)
from wallpaper_effects_generator.ports.command_runner import CommandRunnerPort
from wallpaper_effects_generator.ports.config_resolver import ConfigResolverPort
from wallpaper_effects_generator.ports.effect_loader import EffectLoaderPort
from wallpaper_effects_generator.ports.image_manager import ImageManagerPort
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


def test_create_command_runner_returns_port():
    settings = AppSettings(backend=BackendSettings(binary="magick"))
    with patch("shutil.which", return_value="/usr/bin/magick"):
        runner = create_command_runner(settings=settings)
    assert isinstance(runner, CommandRunnerPort)
    assert isinstance(runner, SubprocessCommandRunner)


def test_create_local_processor_with_deps():
    mock_runner = Mock()
    mock_runner.is_available.return_value = True
    mock_runner.get_binary.return_value = "magick"
    processor = create_local_processor(
        command_runner=mock_runner,
        catalog=EffectsCatalog(),
        output_dir=Path("/tmp"),
    )
    assert isinstance(processor, EffectProcessorPort)
    assert isinstance(processor, LocalProcessor)


def test_create_dry_run_processor_with_deps():
    mock_runner = Mock()
    mock_runner.is_available.return_value = True
    mock_runner.get_binary.return_value = "magick"
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


def test_create_command_runner_container_mode():
    settings = AppSettings(
        runtime=RuntimeSettings(mode=RuntimeMode.CONTAINER),
        container=ContainerSettings(engine="docker"),
    )
    with patch("shutil.which", return_value="/usr/bin/docker"):
        runner = create_command_runner(settings=settings)
    assert isinstance(runner, CommandRunnerPort)
    assert isinstance(runner, OCICommandRunner)


def test_create_oci_command_runner_returns_port():
    settings = AppSettings(container=ContainerSettings(engine="docker"))
    with patch("shutil.which", return_value="/usr/bin/docker"):
        runner = create_oci_command_runner(settings=settings)
    assert isinstance(runner, CommandRunnerPort)
    assert isinstance(runner, OCICommandRunner)


def test_create_container_processor_returns_port():
    mock_runner = Mock()
    mock_runner.is_available.return_value = True
    mock_runner.get_binary.return_value = "docker"
    processor = create_container_processor(
        command_runner=mock_runner,
        catalog=EffectsCatalog(),
        output_dir=Path("/tmp"),
        container_settings=ContainerSettings(engine="docker"),
    )
    from wallpaper_effects_generator.adapters.container_processor import ContainerProcessor
    assert isinstance(processor, EffectProcessorPort)
    assert isinstance(processor, ContainerProcessor)


def test_create_image_manager_returns_port():
    mock_runner = Mock()
    mock_runner.is_available.return_value = True
    mock_runner.get_binary.return_value = "docker"
    mgr = create_image_manager(command_runner=mock_runner)
    assert isinstance(mgr, ImageManagerPort)
    assert isinstance(mgr, DockerImageManager)
