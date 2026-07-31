from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from color_scheme_generator.adapters.container_processor import _CONTAINER_ENV, ContainerProcessor
from color_scheme_generator.domain.enums import Backend, ColorFormat, RuntimeMode
from color_scheme_generator.domain.exceptions import (
    ContainerImageNotFoundError,
    ContainerTimeoutError,
    InvalidImageError,
)
from color_scheme_generator.domain.models import (
    AppSettings,
    ContainerSettings,
    GenerationRequest,
    GenerationResult,
    GenerationSettings,
    GeneratorConfig,
    OutputSettings,
    RuntimeSettings,
)
from color_scheme_generator.ports.processor import ColorSchemeProcessorPort


def _make_settings(**overrides: object) -> AppSettings:
    return AppSettings(
        output=OutputSettings(
            directory=Path("/tmp/out"),
            default_formats=(),
            overwrite=True,
        ),
        generation=GenerationSettings(
            backend=Backend.CUSTOM,
            default_params={},
        ),
        runtime=RuntimeSettings(
            mode=RuntimeMode.LOCAL,
        ),
        container=ContainerSettings(
            engine="docker",
            image_prefix="csg",
            image_tag="latest",
            timeout_seconds=60,
            memory_limit="512m",
            mount_timeout_seconds=30,
        ),
    )


def _make_request(
    backend: Backend = Backend.CUSTOM,
    params: dict[str, str] | None = None,
    formats: tuple[ColorFormat, ...] = (ColorFormat.JSON,),
) -> GenerationRequest:
    config = GeneratorConfig(
        backend=backend,
        params=params or {},
        formats=formats,
        output_dir=Path("/tmp/output"),
    )
    return GenerationRequest(
        image_path=Path("/tmp/wallpaper.png"),
        config=config,
    )


def _setup_test_env(tmp_path: Path) -> tuple[Path, Path, ContainerProcessor]:
    img = tmp_path / "input" / "wallpaper.png"
    img.parent.mkdir(parents=True, exist_ok=True)
    img.write_text("dummy")
    tdir = tmp_path / "templates"
    tdir.mkdir(parents=True, exist_ok=True)
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    mock_runtime = _make_mock_runtime()
    processor = ContainerProcessor(
        mock_runtime,
        default_settings_path=tmp_path / "settings.toml",
    )
    (tmp_path / "settings.toml").write_text("")
    (tmp_path / "defaults" / "templates").mkdir(parents=True, exist_ok=True)
    return tdir, output_dir, processor


def _make_mock_runtime() -> MagicMock:
    runtime = MagicMock()
    runtime.image_exists.return_value = True
    runtime.run.return_value = MagicMock(
        return_code=0,
        stdout="",
        stderr="",
        duration=0.5,
    )
    return runtime


class TestContainerProcessorIsInstance:
    def test_isinstance_check_passes(self) -> None:
        mock_runtime = MagicMock()
        processor = ContainerProcessor(mock_runtime)
        assert isinstance(processor, ColorSchemeProcessorPort)


class TestContainerProcessorGenerate:
    def test_preflight_raises_image_not_found(self, tmp_path: Path) -> None:
        mock_runtime = _make_mock_runtime()
        mock_runtime.image_exists.return_value = False
        processor = ContainerProcessor(mock_runtime)
        settings = _make_settings()
        request = _make_request()

        with pytest.raises(ContainerImageNotFoundError) as exc_info:
            processor.process_generate(request, settings)

        assert exc_info.value.backend == Backend.CUSTOM

    def test_root_filesystem_guard_raises_invalid_image(self, tmp_path: Path) -> None:
        mock_runtime = _make_mock_runtime()
        processor = ContainerProcessor(mock_runtime)
        settings = _make_settings()
        request = _make_request()
        request = GenerationRequest(
            image_path=Path("/hostname"),
            config=request.config,
        )

        with pytest.raises(InvalidImageError) as exc_info:
            processor.process_generate(request, settings)

        assert "Cannot mount filesystem root" in str(exc_info.value)

    def test_temp_toml_cleaned_up_on_success(self, tmp_path: Path) -> None:
        templates_dir, output_dir, processor = _setup_test_env(tmp_path)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=tmp_path / "input" / "wallpaper.png",
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        temp_files_before = set(tmp_path.rglob("*.toml"))

        result = processor.process_generate(request, settings)

        temp_files_after = set(tmp_path.rglob("*.toml"))
        assert temp_files_before == temp_files_after
        assert result.success is True

    def test_temp_toml_cleaned_up_on_failure(self, tmp_path: Path) -> None:
        mock_runtime = _make_mock_runtime()
        mock_runtime.image_exists.return_value = False
        processor = ContainerProcessor(mock_runtime)
        settings = _make_settings()
        request = _make_request()

        temp_files_before = set(tmp_path.rglob("*.toml"))

        with pytest.raises(ContainerImageNotFoundError):
            processor.process_generate(request, settings)

        temp_files_after = set(tmp_path.rglob("*.toml"))
        assert temp_files_before == temp_files_after

    def test_constructs_four_mounts(self, tmp_path: Path) -> None:
        img = tmp_path / "img.png"
        img.write_text("dummy")
        tdir = tmp_path / "templates"
        tdir.mkdir()
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        mock_runtime = MagicMock()
        mock_runtime.image_exists.return_value = True

        container_result = MagicMock(return_code=0, stdout="", stderr="", duration=0.3)
        mock_runtime.run.return_value = container_result

        template_dir_resolver = MagicMock()
        template_dir_resolver.resolve.return_value = tdir

        processor = ContainerProcessor(
            mock_runtime, template_dir_resolver=template_dir_resolver
        )
        settings = _make_settings()
        request = GenerationRequest(
            image_path=img,
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        result = processor.process_generate(request, settings)

        assert result.success is True
        call_kwargs = mock_runtime.run.call_args[1]
        mounts = call_kwargs.get("mounts")
        if mounts is None:
            args = mock_runtime.run.call_args[0]
            mounts = args[2] if len(args) > 2 else []
        assert len(mounts) == 4

    def test_inner_command_has_no_runtime_flag(self, tmp_path: Path) -> None:
        templates_dir, output_dir, processor = _setup_test_env(tmp_path)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=tmp_path / "input" / "wallpaper.png",
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        processor.process_generate(request, settings)

        call_args = processor._container_runtime.run.call_args
        command = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("command", [])
        assert "--runtime" not in command
        assert command[0] == "csg"
        assert command[1] == "generate"

    def test_params_forwarded_verbatim(self, tmp_path: Path) -> None:
        templates_dir, output_dir, processor = _setup_test_env(tmp_path)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=tmp_path / "input" / "wallpaper.png",
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={"saturation": "1.0", "contrast": "0.8"},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        processor.process_generate(request, settings)

        call_args = processor._container_runtime.run.call_args
        command = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("command", [])
        cmd_str = " ".join(command)
        assert "--param saturation=1.0" in cmd_str
        assert "--param contrast=0.8" in cmd_str

    def test_timeout_maps_to_container_timeout_error(self, tmp_path: Path) -> None:
        mock_runtime = MagicMock()
        mock_runtime.image_exists.return_value = True
        mock_runtime.run.side_effect = ContainerTimeoutError()

        tdir = tmp_path / "templates"
        tdir.mkdir()
        img = tmp_path / "img.png"
        img.write_text("dummy")
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        (tmp_path / "defaults" / "templates").mkdir(parents=True, exist_ok=True)

        processor = ContainerProcessor(
            mock_runtime, default_settings_path=tmp_path / "settings.toml"
        )
        (tmp_path / "settings.toml").write_text("")
        settings = _make_settings()
        request = GenerationRequest(
            image_path=img,
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        result = processor.process_generate(request, settings)

        assert result.success is False
        assert "timed out" in result.stderr
        assert result.return_code == -1

    def test_oci_operation_timeout_via_container_runtime_port(
        self, tmp_path: Path
    ) -> None:
        from oci_runtime.domain.exceptions import OperationTimeoutError

        mock_runtime = MagicMock()
        mock_runtime.image_exists.return_value = True
        mock_runtime.run.side_effect = OperationTimeoutError(
            command=["docker", "run"],
            timeout=30.0,
        )

        tdir = tmp_path / "templates"
        tdir.mkdir()
        img = tmp_path / "img.png"
        img.write_text("dummy")
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        (tmp_path / "defaults" / "templates").mkdir(parents=True, exist_ok=True)

        processor = ContainerProcessor(
            mock_runtime, default_settings_path=tmp_path / "settings.toml"
        )
        (tmp_path / "settings.toml").write_text("")
        settings = _make_settings()
        request = GenerationRequest(
            image_path=img,
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        result = processor.process_generate(request, settings)

        assert result.success is False
        assert "timed out" in result.stderr
        assert result.return_code == -1

    def test_passes_expected_environment(self, tmp_path: Path) -> None:
        templates_dir, output_dir, processor = _setup_test_env(tmp_path)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=tmp_path / "input" / "wallpaper.png",
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        processor.process_generate(request, settings)

        call_kwargs = processor._container_runtime.run.call_args[1]
        env = call_kwargs.get("environment", {})
        assert env == _CONTAINER_ENV

    def test_inner_command_argv_is_accepted_by_cli(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from typer.testing import CliRunner
        from color_scheme_generator.cli.main import app

        templates_dir, output_dir, processor = _setup_test_env(tmp_path)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=tmp_path / "input" / "wallpaper.png",
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        mock_processor = MagicMock()
        mock_processor.process_generate.return_value = MagicMock(success=True)
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.create_local_processor",
            lambda *a, **kw: mock_processor,
        )
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.create_container_processor",
            lambda *a, **kw: mock_processor,
        )

        processor.process_generate(request, settings)

        call_args = processor._container_runtime.run.call_args
        command = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("command", [])
        cli_argv = command[1:]

        runner = CliRunner()
        result = runner.invoke(app, cli_argv)

        assert result.exit_code == 0, (
            f"Adapter argv rejected by live CLI\n"
            f"  argv: {cli_argv}\n"
            f"  stderr: {result.stderr}"
        )

    def test_returns_generation_result_with_same_contract_as_local_processor(
        self, tmp_path: Path
    ) -> None:
        templates_dir, output_dir, processor = _setup_test_env(tmp_path)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=tmp_path / "input" / "wallpaper.png",
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        result = processor.process_generate(request, settings)

        assert isinstance(result, GenerationResult)
        assert hasattr(result, "success")
        assert hasattr(result, "color_scheme")
        assert hasattr(result, "output_files")
        assert hasattr(result, "backend")
        assert hasattr(result, "stderr")
        assert hasattr(result, "return_code")
        assert hasattr(result, "duration")


class TestContainerProcessorShow:
    def test_show_mode_does_not_mount_output_dir(self, tmp_path: Path) -> None:
        tdir = tmp_path / "templates"
        tdir.mkdir()
        img = tmp_path / "img.png"
        img.write_text("dummy")
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        mock_runtime = MagicMock()
        mock_runtime.image_exists.return_value = True
        container_result = MagicMock(
            return_code=0,
            stdout=json.dumps(
                {
                    "background": {"hex": "#000000", "rgb": [0, 0, 0]},
                    "foreground": {"hex": "#ffffff", "rgb": [255, 255, 255]},
                    "cursor": {"hex": "#00ff00", "rgb": [0, 255, 0]},
                    "colors": [
                        {"hex": "#000000", "rgb": [0, 0, 0]}
                        for _ in range(16)
                    ],
                    "source_image": "/input/wallpaper.png",
                    "backend": "custom",
                    "generated_at": "2024-01-01T00:00:00",
                }
            ),
            stderr="",
            duration=0.3,
        )
        mock_runtime.run.return_value = container_result

        processor = ContainerProcessor(
            mock_runtime, default_settings_path=tmp_path / "settings.toml"
        )
        (tmp_path / "settings.toml").write_text("")
        (tmp_path / "defaults" / "templates").mkdir(parents=True, exist_ok=True)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=img,
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        result = processor.process_show(request, settings)

        assert result.success is True
        call_args = mock_runtime.run.call_args
        command = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("command", [])
        cmd_str = " ".join(command)
        assert cmd_str.startswith("csg show")
        assert "-o" not in cmd_str.replace("-o ", "")

    def test_show_inner_command_has_no_runtime_flag(self, tmp_path: Path) -> None:
        tdir = tmp_path / "templates"
        tdir.mkdir()
        img = tmp_path / "img.png"
        img.write_text("dummy")
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        mock_runtime = MagicMock()
        mock_runtime.image_exists.return_value = True
        container_result = MagicMock(return_code=0, stdout="{}", stderr="", duration=0.3)
        mock_runtime.run.return_value = container_result

        processor = ContainerProcessor(
            mock_runtime, default_settings_path=tmp_path / "settings.toml"
        )
        (tmp_path / "settings.toml").write_text("")
        (tmp_path / "defaults" / "templates").mkdir(parents=True, exist_ok=True)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=img,
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        processor.process_show(request, settings)

        call_args = mock_runtime.run.call_args
        command = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("command", [])
        assert "--runtime" not in command
        assert command[0] == "csg"
        assert command[1] == "show"

    def test_passes_expected_environment(self, tmp_path: Path) -> None:
        tdir = tmp_path / "templates"
        tdir.mkdir()
        img = tmp_path / "img.png"
        img.write_text("dummy")
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        mock_runtime = MagicMock()
        mock_runtime.image_exists.return_value = True
        container_result = MagicMock(return_code=0, stdout="{}", stderr="", duration=0.3)
        mock_runtime.run.return_value = container_result

        processor = ContainerProcessor(
            mock_runtime, default_settings_path=tmp_path / "settings.toml"
        )
        (tmp_path / "settings.toml").write_text("")
        (tmp_path / "defaults" / "templates").mkdir(parents=True, exist_ok=True)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=img,
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        processor.process_show(request, settings)

        call_kwargs = mock_runtime.run.call_args[1]
        env = call_kwargs.get("environment", {})
        assert env == _CONTAINER_ENV


class TestContainerProcessorTempToml:
    def test_chmod_failure_logs_warning_and_continues(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        templates_dir, output_dir, processor = _setup_test_env(tmp_path)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=tmp_path / "input" / "wallpaper.png",
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        import logging
        caplog.set_level(logging.WARNING)
        with patch("os.chmod", side_effect=OSError("permission denied")):
            result = processor.process_generate(request, settings)

        assert result.success is True
        assert "Failed to chmod" in caplog.text

    def test_temp_toml_is_world_readable(self, tmp_path: Path) -> None:
        templates_dir, output_dir, processor = _setup_test_env(tmp_path)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=tmp_path / "input" / "wallpaper.png",
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.JSON,),
                output_dir=output_dir,
            ),
        )

        toml_paths_before = sorted(tmp_path.rglob("*.toml"))

        processor.process_generate(request, settings)

        toml_paths_after = sorted(tmp_path.rglob("*.toml"))
        toml_files_created = set(toml_paths_after) - set(toml_paths_before)

        for toml_path in toml_files_created:
            mode = os.stat(toml_path).st_mode & 0o777
            assert mode == 0o644, f"Expected 0o644, got {oct(mode)} for {toml_path}"


class TestParseColorSchemeFromJson:
    def _make_processor(self) -> ContainerProcessor:
        return ContainerProcessor(MagicMock())

    def test_parses_backend_as_enum(self) -> None:
        raw = json.dumps({
            "background": {"hex": "#000000", "rgb": [0, 0, 0]},
            "foreground": {"hex": "#ffffff", "rgb": [255, 255, 255]},
            "cursor": {"hex": "#00ff00", "rgb": [0, 255, 0]},
            "colors": [{"hex": "#000000", "rgb": [0, 0, 0]}] * 16,
            "source_image": "/input/test.jpg",
            "backend": "pywal",
            "generated_at": "2024-01-01T00:00:00",
        })
        processor = self._make_processor()
        cs = processor._parse_color_scheme_from_json(raw)
        assert cs is not None
        assert isinstance(cs.backend, Backend)
        assert cs.backend == Backend.PYWAL

    def test_parses_generated_at_as_datetime(self) -> None:
        raw = json.dumps({
            "background": {"hex": "#000000", "rgb": [0, 0, 0]},
            "foreground": {"hex": "#ffffff", "rgb": [255, 255, 255]},
            "cursor": {"hex": "#00ff00", "rgb": [0, 255, 0]},
            "colors": [{"hex": "#000000", "rgb": [0, 0, 0]}] * 16,
            "source_image": "/input/test.jpg",
            "backend": "pywal",
            "generated_at": "2024-01-01T00:00:00",
        })
        processor = self._make_processor()
        cs = processor._parse_color_scheme_from_json(raw)
        assert cs is not None
        assert isinstance(cs.generated_at, datetime)
        assert cs.generated_at.isoformat() == "2024-01-01T00:00:00"

    def test_returns_none_for_empty_input(self) -> None:
        processor = self._make_processor()
        assert processor._parse_color_scheme_from_json("") is None
        assert processor._parse_color_scheme_from_json("   ") is None

    def test_returns_none_for_malformed_json(self) -> None:
        processor = self._make_processor()
        assert processor._parse_color_scheme_from_json("not json") is None

    def test_returns_none_for_missing_backend(self) -> None:
        raw = json.dumps({
            "background": {"hex": "#000000", "rgb": [0, 0, 0]},
            "foreground": {"hex": "#ffffff", "rgb": [255, 255, 255]},
            "cursor": {"hex": "#00ff00", "rgb": [0, 255, 0]},
            "colors": [{"hex": "#000000", "rgb": [0, 0, 0]}] * 16,
            "source_image": "/input/test.jpg",
            "generated_at": "2024-01-01T00:00:00",
        })
        processor = self._make_processor()
        assert processor._parse_color_scheme_from_json(raw) is None

    def test_returns_none_for_invalid_backend_enum(self) -> None:
        raw = json.dumps({
            "background": {"hex": "#000000", "rgb": [0, 0, 0]},
            "foreground": {"hex": "#ffffff", "rgb": [255, 255, 255]},
            "cursor": {"hex": "#00ff00", "rgb": [0, 255, 0]},
            "colors": [{"hex": "#000000", "rgb": [0, 0, 0]}] * 16,
            "source_image": "/input/test.jpg",
            "backend": "nonexistent_backend",
            "generated_at": "2024-01-01T00:00:00",
        })
        processor = self._make_processor()
        assert processor._parse_color_scheme_from_json(raw) is None
