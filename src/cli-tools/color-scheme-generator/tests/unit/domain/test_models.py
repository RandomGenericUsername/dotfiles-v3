from __future__ import annotations

from datetime import datetime
from pathlib import Path, PurePosixPath

import pytest

from color_scheme_generator.domain.enums import Backend, ColorFormat, RuntimeMode
from color_scheme_generator.domain.models import (
    AppSettings,
    BackendDefinition,
    BackendParameterDefinition,
    Color,
    ColorScheme,
    ContainerMount,
    ContainerResult,
    ContainerSettings,
    GenerationRequest,
    GenerationResult,
    GenerationSettings,
    GeneratorConfig,
    OutputSettings,
    RuntimeSettings,
    TemplateSettings,
)


class TestColor:
    def test_valid_hex_case_preserved(self) -> None:
        c = Color("#FF0000", (255, 0, 0))
        assert c.hex == "#FF0000"

    def test_missing_hash_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            Color("ff0000", (255, 0, 0))

    def test_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            Color("#ff00", (255, 0, 0))

    def test_invalid_chars_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            Color("#GG0000", (255, 0, 0))

    def test_lowercase_hex_preserved(self) -> None:
        c = Color("#ff0000", (255, 0, 0))
        assert c.hex == "#ff0000"

    def test_rgb_clamped_above(self) -> None:
        c = Color("#ff0000", (300, 0, 0))
        assert c.rgb == (255, 0, 0)

    def test_rgb_clamped_below(self) -> None:
        c = Color("#ff0000", (-10, 0, 0))
        assert c.rgb == (0, 0, 0)

    def test_adjust_saturation_reduces(self) -> None:
        c = Color("#ff0000", (255, 0, 0))
        result = c.adjust_saturation(0.5)
        assert isinstance(result, Color)
        assert result.rgb != c.rgb
        assert result.hex != c.hex
        assert result.hex == f"#{result.rgb[0]:02x}{result.rgb[1]:02x}{result.rgb[2]:02x}"

    def test_adjust_saturation_immutable(self) -> None:
        c = Color("#ff0000", (255, 0, 0))
        original_rgb = c.rgb
        c.adjust_saturation(0.5)
        assert c.rgb == original_rgb

    def test_rgb_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="rgb must be a 3-tuple"):
            Color("#ff0000", (255, 0, 0, 0))
        with pytest.raises(ValueError, match="rgb must be a 3-tuple"):
            Color("#ff0000", (255, 0))

    def test_rgb_clamped_recomputes_hex(self) -> None:
        c = Color("#00ff00", (300, 0, 0))
        assert c.rgb == (255, 0, 0)
        assert c.hex == "#ff0000"

    def test_float_rgb_coerced_to_int(self) -> None:
        c = Color("#ff0000", (127.5, 0, 0))
        assert isinstance(c.rgb[0], int)

    def test_trailing_newline_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            Color("#ff0000\n", (255, 0, 0))


class TestColorScheme:
    def test_fields(self) -> None:
        bg = Color("#000000", (0, 0, 0))
        fg = Color("#ffffff", (255, 255, 255))
        cursor = Color("#00ff00", (0, 255, 0))
        colors = tuple(Color("#000000", (0, 0, 0)) for _ in range(16))
        scheme = ColorScheme(
            background=bg,
            foreground=fg,
            cursor=cursor,
            colors=colors,
            source_image=Path("/tmp/wallpaper.png"),
            backend=Backend.CUSTOM,
            generated_at=datetime(2024, 1, 1),
        )
        assert scheme.background == bg
        assert scheme.foreground == fg
        assert scheme.cursor == cursor
        assert len(scheme.colors) == 16
        assert scheme.source_image == Path("/tmp/wallpaper.png")
        assert scheme.backend == Backend.CUSTOM
        assert scheme.generated_at == datetime(2024, 1, 1)

    def test_wrong_color_count_raises(self) -> None:
        bg = Color("#000000", (0, 0, 0))
        fg = Color("#ffffff", (255, 255, 255))
        cursor = Color("#00ff00", (0, 255, 0))
        with pytest.raises(ValueError, match="exactly 16 colors"):
            ColorScheme(
                background=bg,
                foreground=fg,
                cursor=cursor,
                colors=tuple(Color("#000000", (0, 0, 0)) for _ in range(15)),
                source_image=Path("/tmp/wallpaper.png"),
                backend=Backend.CUSTOM,
                generated_at=datetime(2024, 1, 1),
            )


class TestGeneratorConfig:
    def test_fields(self) -> None:
        config = GeneratorConfig(
            backend=Backend.PYWAL,
            params={},
            formats=(ColorFormat.JSON,),
            output_dir=Path("/tmp/output"),
        )
        assert config.backend == Backend.PYWAL
        assert config.params == {}
        assert config.formats == (ColorFormat.JSON,)
        assert config.output_dir == Path("/tmp/output")


class TestGenerationRequest:
    def test_fields(self) -> None:
        config = GeneratorConfig(
            backend=Backend.PYWAL,
            params={},
            formats=(ColorFormat.JSON,),
            output_dir=Path("/tmp/output"),
        )
        req = GenerationRequest(
            image_path=Path("/tmp/wallpaper.png"),
            config=config,
        )
        assert req.image_path == Path("/tmp/wallpaper.png")
        assert req.config == config


class TestGenerationResult:
    def test_fields(self) -> None:
        bg = Color("#000000", (0, 0, 0))
        scheme = ColorScheme(
            background=bg,
            foreground=Color("#ffffff", (255, 255, 255)),
            cursor=Color("#00ff00", (0, 255, 0)),
            colors=tuple(Color("#000000", (0, 0, 0)) for _ in range(16)),
            source_image=Path("/tmp/wallpaper.png"),
            backend=Backend.CUSTOM,
            generated_at=datetime(2024, 1, 1),
        )
        result = GenerationResult(
            success=True,
            color_scheme=scheme,
            output_files=(Path("/tmp/output/colors.json"),),
            backend=Backend.CUSTOM,
            stderr="",
            return_code=0,
            duration=0.5,
        )
        assert result.success is True
        assert result.color_scheme == scheme
        assert result.output_files == (Path("/tmp/output/colors.json"),)
        assert result.backend == Backend.CUSTOM
        assert result.stderr == ""
        assert result.return_code == 0
        assert result.duration == 0.5


class TestBackendParameterDefinition:
    def test_fields(self) -> None:
        param = BackendParameterDefinition(
            name="colors",
            type_="int",
            default=16,
            description="Number of colors",
            required=False,
            choices=("8", "16", "256"),
        )
        assert param.name == "colors"
        assert param.type_ == "int"
        assert param.default == 16
        assert param.description == "Number of colors"
        assert param.required is False
        assert param.choices == ("8", "16", "256")

    def test_no_choices(self) -> None:
        param = BackendParameterDefinition(
            name="backend",
            type_="str",
            default=None,
            description="Backend engine",
            required=True,
            choices=None,
        )
        assert param.choices is None

    def test_optional_default(self) -> None:
        param = BackendParameterDefinition(
            name="width",
            type_="int",
            default=None,
            description="Image width",
            required=False,
            choices=None,
        )
        assert param.default is None


class TestBackendDefinition:
    def test_fields(self) -> None:
        params = (
            BackendParameterDefinition(
                name="colors",
                type_="int",
                default=16,
                description="Number of colors",
                required=False,
                choices=None,
            ),
        )
        bd = BackendDefinition(
            backend=Backend.CUSTOM,
            display_name="Custom Backend",
            description="A custom color extraction backend",
            parameters=params,
            min_version="1.0.0",
        )
        assert bd.backend == Backend.CUSTOM
        assert bd.display_name == "Custom Backend"
        assert bd.description == "A custom color extraction backend"
        assert bd.parameters == params
        assert bd.min_version == "1.0.0"

    def test_empty_parameters(self) -> None:
        bd = BackendDefinition(
            backend=Backend.PYWAL,
            display_name="Pywal",
            description="",
            parameters=(),
            min_version="3.0.0",
        )
        assert bd.parameters == ()


class TestOutputSettings:
    def test_fields(self) -> None:
        s = OutputSettings(
            directory=Path("/tmp/output"),
            default_formats=(ColorFormat.JSON, ColorFormat.YAML),
            overwrite=True,
        )
        assert s.directory == Path("/tmp/output")
        assert s.default_formats == (ColorFormat.JSON, ColorFormat.YAML)
        assert s.overwrite is True


class TestGenerationSettings:
    def test_fields(self) -> None:
        s = GenerationSettings(
            backend=Backend.CUSTOM,
            default_params={"colors": 16},
        )
        assert s.backend == Backend.CUSTOM
        assert s.default_params == {"colors": 16}

    def test_empty_params(self) -> None:
        s = GenerationSettings(backend=Backend.PYWAL, default_params={})
        assert s.default_params == {}


class TestTemplateSettings:
    def test_with_dirs(self) -> None:
        s = TemplateSettings(
            templates_dir=Path("/templates"),
            custom_templates_dir=Path("/custom"),
        )
        assert s.templates_dir == Path("/templates")
        assert s.custom_templates_dir == Path("/custom")

    def test_none_dirs(self) -> None:
        s = TemplateSettings(templates_dir=None, custom_templates_dir=None)
        assert s.templates_dir is None
        assert s.custom_templates_dir is None


class TestRuntimeSettings:
    def test_fields(self) -> None:
        s = RuntimeSettings(mode=RuntimeMode.LOCAL)
        assert s.mode == RuntimeMode.LOCAL


class TestContainerSettings:
    def test_fields(self) -> None:
        s = ContainerSettings(
            engine="docker",
            image_prefix="csg",
            image_tag="latest",
            timeout_seconds=300,
            memory_limit="512m",
            mount_timeout_seconds=30,
        )
        assert s.engine == "docker"
        assert s.image_prefix == "csg"
        assert s.image_tag == "latest"
        assert s.timeout_seconds == 300
        assert s.memory_limit == "512m"
        assert s.mount_timeout_seconds == 30


class TestAppSettings:
    def test_composition(self) -> None:
        output = OutputSettings(
            directory=Path("/tmp/output"),
            default_formats=(ColorFormat.JSON,),
            overwrite=False,
        )
        generation = GenerationSettings(backend=Backend.CUSTOM, default_params={})
        template = TemplateSettings(templates_dir=None, custom_templates_dir=None)
        runtime = RuntimeSettings(mode=RuntimeMode.LOCAL)
        container = ContainerSettings(
            engine="docker",
            image_prefix="csg",
            image_tag="latest",
            timeout_seconds=300,
            memory_limit="512m",
            mount_timeout_seconds=30,
        )
        settings = AppSettings(
            output=output,
            generation=generation,
            template=template,
            runtime=runtime,
            container=container,
        )
        assert settings.output == output
        assert settings.generation == generation
        assert settings.template == template
        assert settings.runtime == runtime
        assert settings.container == container


class TestContainerMount:
    def test_fields(self) -> None:
        m = ContainerMount(
            source=Path("/host/path"),
            target=PurePosixPath("/container/path"),
            read_only=True,
        )
        assert m.source == Path("/host/path")
        assert m.target == PurePosixPath("/container/path")
        assert m.read_only is True

    def test_read_write(self) -> None:
        m = ContainerMount(
            source=Path("/src"),
            target=PurePosixPath("/dst"),
            read_only=False,
        )
        assert m.read_only is False


class TestContainerResult:
    def test_fields(self) -> None:
        r = ContainerResult(
            return_code=0,
            stdout="output",
            stderr="",
            duration=1.5,
        )
        assert r.return_code == 0
        assert r.stdout == "output"
        assert r.stderr == ""
        assert r.duration == 1.5

    def test_error_result(self) -> None:
        r = ContainerResult(
            return_code=1,
            stdout="",
            stderr="error occurred",
            duration=2.0,
        )
        assert r.return_code == 1
        assert r.stderr == "error occurred"
