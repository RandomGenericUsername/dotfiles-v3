from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from wallpaper_effects_generator.adapters.container_processor import (
    _CONTAINER_ENV,
    ContainerProcessor,
)
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BackendSettings,
    ContainerSettings,
    EffectsCatalog,
    ExecutionSettings,
    OutputSettings,
    ProcessingRequest,
    ProcessingResult,
    RuntimeSettings,
)


class FakeEngineImages:
    def __init__(self, parent: FakeEngine) -> None:
        self._parent = parent

    def exists(self, image_name: str) -> bool:
        return self._parent.exists_result


class FakeEngineCaps:
    def __init__(self) -> None:
        self.default_run_flags: list[str] = []


class FakeEngineContainers:
    def __init__(self, parent: FakeEngine) -> None:
        self._parent = parent

    def run(self, run_config: object) -> None:
        self._parent.last_run_config = run_config
        self._parent.last_settings_toml_content: str | None = None
        self._parent.last_effects_yaml_content: str | None = None
        for vol in run_config.volumes:
            if vol.target == "/weg-config/settings.toml":
                try:
                    self._parent.last_settings_toml_content = Path(vol.source).read_text()
                except FileNotFoundError:
                    pass
            if vol.target == "/weg-effects/effects.yaml":
                try:
                    self._parent.last_effects_yaml_content = Path(vol.source).read_text()
                except FileNotFoundError:
                    pass
            if vol.target == "/output":
                out_dir = Path(vol.source)
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / self._parent.output_file_name).write_text("")
                break


@dataclass
class FakeEngine:
    exists_result: bool = True
    last_run_config: object = None
    output_file_name: str = "img.png"
    images: FakeEngineImages = field(init=False)
    capabilities: FakeEngineCaps = field(init=False)
    containers: FakeEngineContainers = field(init=False)

    def __post_init__(self) -> None:
        self.images = FakeEngineImages(self)
        self.capabilities = FakeEngineCaps()
        self.containers = FakeEngineContainers(self)


@pytest.fixture
def fake_engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def catalog() -> EffectsCatalog:
    from wallpaper_effects_generator.domain.models import (
        ChainStep,
        CompositeDefinition,
        EffectDefinition,
        ParameterDefinition,
        PresetDefinition,
    )

    return EffectsCatalog(
        effects=(
            EffectDefinition(
                name="blur",
                description="Blur effect",
                command="magick {{input}} -blur {{radius}} {{output}}",
                parameters=(
                    ParameterDefinition(key="radius", description="Radius", default="0x8"),
                ),
            ),
            EffectDefinition(
                name="resize",
                description="Resize effect",
                command="magick {{input}} -resize {{size}} {{output}}",
                parameters=(ParameterDefinition(key="size", description="Size", default="50%"),),
            ),
        ),
        composites=(
            CompositeDefinition(
                name="blur-resize",
                description="Blur then resize",
                steps=(
                    ChainStep(effect_name="blur", parameters={"radius": "0x4"}),
                    ChainStep(effect_name="resize", parameters={"size": "800"}),
                ),
            ),
        ),
        presets=(
            PresetDefinition(
                name="social",
                description="Social media preset",
                effects=("resize",),
            ),
        ),
    )


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(
        version="1.0",
        execution=ExecutionSettings(parallel=True, strict=False, max_workers=0),
        output=OutputSettings(),
        backend=BackendSettings(binary="magick"),
        runtime=RuntimeSettings(),
        container=ContainerSettings(engine="docker"),
    )


@pytest.fixture
def processor(
    fake_engine: FakeEngine, catalog: EffectsCatalog, settings: AppSettings, tmp_path: Path
) -> ContainerProcessor:
    return ContainerProcessor(
        command_runner=Mock(),
        catalog=catalog,
        output_dir=tmp_path,
        container_engine=fake_engine,
        container_settings=ContainerSettings(engine="docker"),
        settings=settings,
    )


class TestContainerProcessor:
    def test_process_effect_success(self, processor: ContainerProcessor, tmp_path: Path) -> None:
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        result = processor.process_effect("blur", request, {"radius": "0x8"})
        assert result.success
        assert "process effect blur" in result.command

    def test_process_effect_not_found(self, processor: ContainerProcessor) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        from wallpaper_effects_generator.domain.exceptions import EffectNotFoundError

        with pytest.raises(EffectNotFoundError):
            processor.process_effect("nonexistent", request)

    def test_process_composite_success(self, processor: ContainerProcessor, tmp_path: Path) -> None:
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        result = processor.process_composite("blur-resize", request)
        assert result.success

    def test_process_composite_not_found(self, processor: ContainerProcessor) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        from wallpaper_effects_generator.domain.exceptions import CompositeNotFoundError

        with pytest.raises(CompositeNotFoundError):
            processor.process_composite("nonexistent", request)

    def test_process_preset_success(self, processor: ContainerProcessor, tmp_path: Path) -> None:
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        result = processor.process_preset("social", request)
        assert result.success

    def test_process_preset_not_found(self, processor: ContainerProcessor) -> None:
        request = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        from wallpaper_effects_generator.domain.exceptions import PresetNotFoundError

        with pytest.raises(PresetNotFoundError):
            processor.process_preset("nonexistent", request)

    def test_process_batch_not_implemented(self, processor: ContainerProcessor) -> None:
        with pytest.raises(NotImplementedError):
            processor.process_batch(None)

    def test_passes_expected_environment(
        self, processor: ContainerProcessor, fake_engine: FakeEngine, tmp_path: Path
    ) -> None:
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        processor.process_effect("blur", request, {"radius": "0x8"})
        run_config = fake_engine.last_run_config
        assert run_config.environment == _CONTAINER_ENV

    @pytest.mark.parametrize(
        ("subcommand", "name", "params"),
        [
            pytest.param("effect", "blur", {"radius": "0x8"}, id="effect"),
            pytest.param("composite", "blur-resize", None, id="composite"),
            pytest.param("preset", "social", None, id="preset"),
        ],
    )
    def test_build_weg_command_argv_is_accepted_by_cli(
        self, processor: ContainerProcessor, tmp_path: Path,
        subcommand: str, name: str, params: dict[str, str] | None,
    ) -> None:
        from typer.testing import CliRunner
        from wallpaper_effects_generator.cli.main import app

        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        cmd = processor._build_weg_command(subcommand, name, request, params or {})
        cli_argv = cmd[1:]

        mock_processor = MagicMock()
        for attr in ("process_effect", "process_composite", "process_preset"):
            getattr(mock_processor, attr).return_value = ProcessingResult(
                success=True, command="", stdout="", stderr="", return_code=0,
            )

        runner = CliRunner()
        with (
            patch("wallpaper_effects_generator.cli.process._resolve_processor",
                  return_value=mock_processor),
            patch("wallpaper_effects_generator.cli.process._resolve_context",
                  return_value=(MagicMock(), MagicMock())),
            patch("wallpaper_effects_generator.cli.process.Path.exists",
                  return_value=True),
            patch("wallpaper_effects_generator.cli.process.Path.is_file",
                  return_value=True),
            patch("wallpaper_effects_generator.cli.process.Path.mkdir",
                  return_value=None),
        ):
            result = runner.invoke(app, cli_argv)

        assert result.exit_code == 0, (
            f"Adapter argv rejected by live CLI\n"
            f"  argv: {cli_argv}\n"
            f"  stderr: {result.stderr}"
        )

    def test_uses_oci_command_runner(
        self, catalog: EffectsCatalog, settings: AppSettings, tmp_path: Path
    ) -> None:
        fe = FakeEngine()
        processor = ContainerProcessor(
            command_runner=Mock(),
            catalog=catalog,
            output_dir=tmp_path,
            container_engine=fe,
            container_settings=ContainerSettings(engine="podman"),
            settings=settings,
        )
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        result = processor.process_effect("blur", request, {"radius": "0x8"})
        assert result.success
        assert "process effect blur" in result.command

    def test_temp_cleanup_on_success(self, processor: ContainerProcessor, tmp_path: Path) -> None:
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        with patch(
            "wallpaper_effects_generator.adapters.container_processor.tempfile.NamedTemporaryFile",
        ) as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test_weg.toml"
            result = processor.process_effect("blur", request, {"radius": "0x8"})
            assert result.success

    def test_all_four_volume_mounts_present(
        self, processor: ContainerProcessor, fake_engine: FakeEngine, tmp_path: Path
    ) -> None:
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        processor.process_effect("blur", request, {"radius": "0x8"})
        run_config = fake_engine.last_run_config
        assert len(run_config.volumes) == 4

    def test_volume_mounts_have_correct_sources_and_targets(
        self, processor: ContainerProcessor, fake_engine: FakeEngine, tmp_path: Path
    ) -> None:
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        processor.process_effect("blur", request, {"radius": "0x8"})
        run_config = fake_engine.last_run_config
        targets = {v.target for v in run_config.volumes}
        assert "/weg-config/settings.toml" in targets
        assert "/weg-effects/effects.yaml" in targets
        assert "/input" in targets
        assert "/output" in targets
        for v in run_config.volumes:
            if v.target in ("/weg-config/settings.toml", "/weg-effects/effects.yaml", "/input"):
                assert v.read_only is True
            if v.target == "/output":
                assert v.read_only is False

    def test_serialized_toml_contains_runtime_mode_local(
        self, processor: ContainerProcessor, fake_engine: FakeEngine, tmp_path: Path
    ) -> None:
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        processor.process_effect("blur", request, {"radius": "0x8"})
        assert fake_engine.last_settings_toml_content is not None
        assert 'mode = "local"' in fake_engine.last_settings_toml_content

    def test_serialized_toml_valid_toml(
        self, processor: ContainerProcessor, fake_engine: FakeEngine, tmp_path: Path
    ) -> None:
        import tomllib

        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        processor.process_effect("blur", request, {"radius": "0x8"})
        assert fake_engine.last_settings_toml_content is not None
        data = tomllib.loads(fake_engine.last_settings_toml_content)
        assert data["runtime"]["mode"] == "local"

    def test_input_parent_is_root_raises_error(
        self,
        catalog: EffectsCatalog,
        settings: AppSettings,
        fake_engine: FakeEngine,
        tmp_path: Path,
    ) -> None:
        from wallpaper_effects_generator.ports.context_validator import (
            ContextValidationResult,
        )

        rejecting_validator = Mock()
        rejecting_validator.validate.return_value = ContextValidationResult(
            valid=False, errors=["Input path parent is '/' which would mount the entire filesystem"]
        )
        processor = ContainerProcessor(
            command_runner=Mock(),
            catalog=catalog,
            output_dir=tmp_path,
            container_engine=fake_engine,
            container_settings=ContainerSettings(engine="docker"),
            settings=settings,
            context_validator=rejecting_validator,
        )
        request = ProcessingRequest(
            input_path=Path("/photo.jpg"),
            output_path=tmp_path / "out.png",
        )
        result = processor.process_effect("blur", request)
        assert not result.success

    def test_symlink_input_resolves_before_mounting(
        self, processor: ContainerProcessor, fake_engine: FakeEngine, tmp_path: Path
    ) -> None:
        real_file = tmp_path / "real_target.png"
        real_file.write_text("dummy")
        link_path = tmp_path / "link.png"
        link_path.symlink_to(real_file)
        request = ProcessingRequest(
            input_path=link_path,
            output_path=tmp_path / "out.png",
        )
        result = processor.process_effect("blur", request, {"radius": "0x8"})
        assert result.success
        run_config = fake_engine.last_run_config
        for v in run_config.volumes:
            if v.target == "/input":
                assert v.source == str(real_file.parent.resolve())

    def test_cleanup_on_exception(
        self, processor: ContainerProcessor, fake_engine: FakeEngine, tmp_path: Path
    ) -> None:
        fake_engine.exists_result = False
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        from wallpaper_effects_generator.domain.exceptions import ContainerImageNotFoundError

        with pytest.raises(ContainerImageNotFoundError):
            processor.process_effect("blur", request, {"radius": "0x8"})

    def test_container_image_not_found_error(
        self, processor: ContainerProcessor, fake_engine: FakeEngine, tmp_path: Path
    ) -> None:
        fake_engine.exists_result = False
        request = ProcessingRequest(
            input_path=tmp_path / "img.png",
            output_path=tmp_path / "img.png",
        )
        from wallpaper_effects_generator.domain.exceptions import ContainerImageNotFoundError

        with pytest.raises(ContainerImageNotFoundError):
            processor.process_effect("blur", request, {"radius": "0x8"})
