from pathlib import Path

import pytest

from wallpaper_effects_generator.constants import MAX_WORKERS_AUTO
from wallpaper_effects_generator.domain.enums import ItemType, RuntimeMode, Verbosity
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BackendSettings,
    BatchRequest,
    BatchResult,
    ChainStep,
    CommandResult,
    CompositeDefinition,
    ContainerSettings,
    EffectDefinition,
    EffectsCatalog,
    ExecutionSettings,
    OutputSettings,
    ParameterDefinition,
    PresetDefinition,
    ProcessingRequest,
    ProcessingResult,
    RuntimeSettings,
)


class TestEffectDefinition:
    def test_minimal(self) -> None:
        e = EffectDefinition(name="test", description="test effect", command="echo")
        assert e.name == "test"
        assert e.description == "test effect"
        assert e.command == "echo"
        assert e.parameters == ()
        assert e.item_type == ItemType.EFFECT

    def test_with_parameters(self) -> None:
        p = ParameterDefinition(key="size", description="Size", default="100")
        e = EffectDefinition(
            name="resize",
            description="Resize image",
            command="convert {{input}} -resize {{size}} {{output}}",
            parameters=(p,),
        )
        assert e.parameters[0].key == "size"

    def test_frozen(self) -> None:
        e = EffectDefinition(name="a", description="b", command="c")
        with pytest.raises(AttributeError):
            e.name = "new"  # type: ignore[misc]


class TestCompositeDefinition:
    def test_with_steps(self) -> None:
        s = ChainStep(effect_name="resize", parameters={"size": "800"})
        c = CompositeDefinition(
            name="resize-and-crop",
            description="Resize then crop",
            steps=(s,),
        )
        assert c.steps[0].effect_name == "resize"


class TestPresetDefinition:
    def test_with_effects(self) -> None:
        p = PresetDefinition(
            name="social-media",
            description="Social media preset",
            effects=("resize", "watermark"),
        )
        assert p.effects == ("resize", "watermark")


class TestEffectsCatalog:
    def test_empty(self) -> None:
        c = EffectsCatalog()
        assert c.effects == ()
        assert c.composites == ()
        assert c.presets == ()

    def test_with_items(self) -> None:
        e = EffectDefinition(name="blur", description="Blur", command="blur")
        c = EffectsCatalog(effects=(e,))
        assert len(c.effects) == 1


class TestProcessingRequest:
    def test_creation(self) -> None:
        req = ProcessingRequest(
            input_path=Path("/in/img.png"),
            output_path=Path("/out/img.png"),
        )
        assert req.input_path == Path("/in/img.png")
        assert req.params == {}


class TestProcessingResult:
    def test_success(self) -> None:
        r = ProcessingResult(
            success=True,
            command="convert",
            stdout="done",
            stderr="",
            return_code=0,
        )
        assert r.success
        assert r.return_code == 0

    def test_failure(self) -> None:
        r = ProcessingResult(
            success=False,
            command="convert",
            stdout="",
            stderr="error",
            return_code=1,
        )
        assert not r.success
        assert r.return_code == 1

    def test_with_output_path(self) -> None:
        r = ProcessingResult(
            success=True,
            command="convert",
            stdout="done",
            stderr="",
            return_code=0,
            output_path=Path("/out/img.png"),
        )
        assert r.output_path == Path("/out/img.png")


class TestBatchRequest:
    def test_defaults(self) -> None:
        req = BatchRequest(
            input_path=Path("/in"),
            output_dir=Path("/out"),
        )
        assert req.parallel
        assert not req.strict
        assert req.max_workers == MAX_WORKERS_AUTO

    def test_frozen(self) -> None:
        req = BatchRequest(input_path=Path("/in"), output_dir=Path("/out"))
        with pytest.raises(AttributeError):
            req.parallel = False  # type: ignore[misc]

    def test_max_workers_invalid(self) -> None:
        with pytest.raises(ValueError, match="max_workers must be >= 0"):
            BatchRequest(
                input_path=Path("/in"),
                output_dir=Path("/out"),
                max_workers=-5,
            )


class TestBatchResult:
    def test_defaults(self) -> None:
        r = BatchResult()
        assert r.total == 0
        assert r.succeeded == 0
        assert r.failed == 0

    def test_with_results(self) -> None:
        pr = ProcessingResult(
            success=True,
            command="c",
            stdout="",
            stderr="",
            return_code=0,
        )
        r = BatchResult(total=1, succeeded=1, results=(pr,))
        assert r.succeeded == 1
        assert r.results[0].success


class TestAppSettings:
    def test_defaults(self) -> None:
        s = AppSettings()
        assert s.version == "0.1.0"
        assert s.execution.parallel
        assert s.output.verbosity == Verbosity.NORMAL
        assert s.runtime.mode == RuntimeMode.LOCAL
        assert s.container.engine == "docker"

    def test_custom(self) -> None:
        s = AppSettings(
            version="1.0.0",
            execution=ExecutionSettings(parallel=False, max_workers=2),
            runtime=RuntimeSettings(mode=RuntimeMode.CONTAINER),
            container=ContainerSettings(engine="podman"),
        )
        assert s.version == "1.0.0"
        assert not s.execution.parallel
        assert s.runtime.mode == RuntimeMode.CONTAINER
        assert s.container.engine == "podman"


class TestCommandResult:
    def test_creation(self) -> None:
        r = CommandResult(stdout="out", stderr="", return_code=0)
        assert r.stdout == "out"
        assert r.return_code == 0
        assert r.duration == 0.0

    def test_failure(self) -> None:
        r = CommandResult(stdout="", stderr="error", return_code=1, duration=0.5)
        assert r.stderr == "error"
        assert r.duration == 0.5


class TestBackendSettings:
    def test_default_binary(self) -> None:
        s = BackendSettings()
        assert s.binary == "magick"


class TestOutputSettings:
    def test_default(self) -> None:
        s = OutputSettings()
        assert s.verbosity == Verbosity.NORMAL
        assert s.directory is None
