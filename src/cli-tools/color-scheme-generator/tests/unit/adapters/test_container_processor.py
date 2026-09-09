from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
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
    ContainerMount,
    ContainerSettings,
    GenerationRequest,
    GenerationResult,
    GenerationSettings,
    GeneratorConfig,
    OutputSettings,
    RuntimeSettings,
)
from color_scheme_generator.ports.processor import ColorSchemeProcessorPort


@dataclass
class _FakeRunResult:
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.3


class _FakeContainerRuntime:
    """Recording stand-in for ContainerRuntimePort used by ContainerProcessor."""

    def __init__(
        self,
        *,
        image_exists: bool = True,
        run_error: Exception | None = None,
        run_result: _FakeRunResult | None = None,
    ) -> None:
        self._image_exists = image_exists
        self._run_error = run_error
        self._run_result = run_result or _FakeRunResult()
        self.image_exists_calls: list[str] = []
        self.run_calls: list[dict[str, object]] = []
        self.last_run_config: dict[str, object] | None = None
        self.serialized_settings: str | None = None

    def image_exists(self, image: str) -> bool:
        self.image_exists_calls.append(image)
        return self._image_exists

    def run(
        self,
        image: str,
        command: list[str],
        mounts: list[ContainerMount],
        timeout: int,
        environment: dict[str, str] | None = None,
    ) -> _FakeRunResult:
        config: dict[str, object] = {
            "image": image,
            "command": command,
            "mounts": mounts,
            "timeout": timeout,
            "environment": environment,
        }
        self.run_calls.append(config)
        self.last_run_config = config
        for mount in mounts:
            if mount.target == PurePosixPath("/csg-config/settings.toml"):
                self.serialized_settings = Path(mount.source).read_text()
        if self._run_error is not None:
            raise self._run_error
        for mount in mounts:
            if not mount.read_only and mount.target == PurePosixPath("/output"):
                source = Path(mount.source)
                source.mkdir(parents=True, exist_ok=True)
                (source / "colors.json").write_text("dummy")
        return self._run_result


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


def _make_result() -> GenerationResult:
    return GenerationResult(
        success=True,
        color_scheme=None,
        output_files=(),
        backend=Backend.CUSTOM,
        stderr="",
        return_code=0,
        duration=0.3,
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
    processor = ContainerProcessor(
        _FakeContainerRuntime(),
        default_settings_path=tmp_path / "settings.toml",
    )
    (tmp_path / "settings.toml").write_text("")
    (tmp_path / "defaults" / "templates").mkdir(parents=True, exist_ok=True)
    return tdir, output_dir, processor


def _run_call_args(processor: ContainerProcessor) -> dict[str, object]:
    assert processor._container_runtime.last_run_config is not None
    return processor._container_runtime.last_run_config


class TestContainerProcessorIsInstance:
    def test_isinstance_check_passes(self) -> None:
        processor = ContainerProcessor(_FakeContainerRuntime())
        assert isinstance(processor, ColorSchemeProcessorPort)


class TestContainerProcessorGenerate:
    def test_explicit_templates_dir_mounts_requested_dir_not_resolver(
        self, tmp_path: Path
    ) -> None:
        """CLI --templates-dir must reach the /templates bind-mount.

        Regression: process_generate resolved templates through the
        resolver chain and silently IGNORED the explicit CLI flag, so
        ``csg generate --templates-dir <dir> --runtime container`` rendered
        from bundled defaults (spine-templates marker missing in output).
        """
        img = tmp_path / "img.png"
        img.write_text("dummy")
        explicit = tmp_path / "spine-templates"
        explicit.mkdir()
        other = tmp_path / "bundled"
        other.mkdir()
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        fake_runtime = _FakeContainerRuntime()
        template_dir_resolver = MagicMock()
        template_dir_resolver.resolve.return_value = other

        processor = ContainerProcessor(
            fake_runtime,
            template_dir_resolver=template_dir_resolver,
            templates_dir=explicit,
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
        mounts = _run_call_args(processor)["mounts"]
        mount_by_target = {m.target: m for m in mounts}
        assert mount_by_target[PurePosixPath("/templates")].source == explicit
        template_dir_resolver.resolve.assert_not_called()

    def test_preflight_raises_image_not_found(self, tmp_path: Path) -> None:
        fake_runtime = _FakeContainerRuntime(image_exists=False)
        processor = ContainerProcessor(fake_runtime)
        settings = _make_settings()
        request = _make_request()

        with pytest.raises(ContainerImageNotFoundError) as exc_info:
            processor.process_generate(request, settings)

        assert exc_info.value.backend == Backend.CUSTOM
        assert fake_runtime.run_calls == []
        assert len(fake_runtime.image_exists_calls) == 1

    def test_root_filesystem_guard_raises_invalid_image(self, tmp_path: Path) -> None:
        fake_runtime = _FakeContainerRuntime()
        processor = ContainerProcessor(fake_runtime)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=Path("/hostname"),
            config=_make_request().config,
        )

        with pytest.raises(InvalidImageError) as exc_info:
            processor.process_generate(request, settings)

        assert "Cannot mount filesystem root" in str(exc_info.value)
        assert fake_runtime.run_calls == []

    def test_constructs_four_mounts_with_source_target_read_only(self, tmp_path: Path) -> None:
        img = tmp_path / "img.png"
        img.write_text("dummy")
        tdir = tmp_path / "templates"
        tdir.mkdir()
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        fake_runtime = _FakeContainerRuntime()
        template_dir_resolver = MagicMock()
        template_dir_resolver.resolve.return_value = tdir

        processor = ContainerProcessor(fake_runtime, template_dir_resolver=template_dir_resolver)
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
        mounts = _run_call_args(processor)["mounts"]
        assert isinstance(mounts, list)
        mount_by_target = {m.target: m for m in mounts}
        assert set(mount_by_target) == {
            PurePosixPath("/input"),
            PurePosixPath("/output"),
            PurePosixPath("/csg-config/settings.toml"),
            PurePosixPath("/templates"),
        }

        input_mount = mount_by_target[PurePosixPath("/input")]
        assert input_mount.source == img.resolve().parent
        assert input_mount.read_only is True

        output_mount = mount_by_target[PurePosixPath("/output")]
        assert output_mount.source == output_dir
        assert output_mount.read_only is False

        settings_mount = mount_by_target[PurePosixPath("/csg-config/settings.toml")]
        assert settings_mount.target == PurePosixPath("/csg-config/settings.toml")
        assert settings_mount.read_only is True

        templates_mount = mount_by_target[PurePosixPath("/templates")]
        assert templates_mount.source == tdir
        assert templates_mount.read_only is True

    def test_runs_use_expected_environment(self, tmp_path: Path) -> None:
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

        environment = _run_call_args(processor)["environment"]
        assert environment == _CONTAINER_ENV

    def test_serialized_settings_is_valid_toml_with_local_runtime(self, tmp_path: Path) -> None:
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

        serialized = processor._container_runtime.serialized_settings
        assert serialized is not None
        data = tomllib.loads(serialized)
        assert data["runtime"]["mode"] == "local"
        assert data["output"]["directory"] == "/tmp/out"
        assert data["generation"]["backend"] == "custom"
        assert data["container"]["engine"] == "docker"

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
        fake_runtime = _FakeContainerRuntime(image_exists=False)
        processor = ContainerProcessor(fake_runtime)
        settings = _make_settings()
        request = _make_request()

        temp_files_before = set(tmp_path.rglob("*.toml"))

        with pytest.raises(ContainerImageNotFoundError):
            processor.process_generate(request, settings)

        temp_files_after = set(tmp_path.rglob("*.toml"))
        assert temp_files_before == temp_files_after

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

        command = _run_call_args(processor)["command"]
        assert isinstance(command, list)
        assert "--runtime" not in command
        assert command[0] == "csg"
        assert command[1] == "generate"

    def test_inner_command_forwards_adw_css_format(self, tmp_path: Path) -> None:
        templates_dir, output_dir, processor = _setup_test_env(tmp_path)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=tmp_path / "input" / "wallpaper.png",
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(ColorFormat.ADW_CSS,),
                output_dir=output_dir,
            ),
        )

        processor.process_generate(request, settings)

        command = _run_call_args(processor)["command"]
        assert isinstance(command, list)
        assert "--format" in command
        assert command[command.index("--format") + 1] == "adw.css"

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

        command = _run_call_args(processor)["command"]
        assert isinstance(command, list)
        cmd_str = " ".join(command)
        assert "--param saturation=1.0" in cmd_str
        assert "--param contrast=0.8" in cmd_str

    def test_timeout_maps_to_container_timeout_error(self, tmp_path: Path) -> None:
        fake_runtime = _FakeContainerRuntime(run_error=ContainerTimeoutError())
        tdir = tmp_path / "templates"
        tdir.mkdir()
        img = tmp_path / "img.png"
        img.write_text("dummy")
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        (tmp_path / "defaults" / "templates").mkdir(parents=True, exist_ok=True)

        processor = ContainerProcessor(
            fake_runtime, default_settings_path=tmp_path / "settings.toml"
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

    def test_oci_operation_timeout_via_container_runtime_port(self, tmp_path: Path) -> None:
        from oci_runtime.domain.exceptions import OperationTimeoutError

        fake_runtime = _FakeContainerRuntime(
            run_error=OperationTimeoutError(
                command=["docker", "run"],
                timeout=30.0,
            )
        )
        tdir = tmp_path / "templates"
        tdir.mkdir()
        img = tmp_path / "img.png"
        img.write_text("dummy")
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        (tmp_path / "defaults" / "templates").mkdir(parents=True, exist_ok=True)

        processor = ContainerProcessor(
            fake_runtime, default_settings_path=tmp_path / "settings.toml"
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

    def test_fake_runtime_writes_dummy_output_at_output_mount_source(self, tmp_path: Path) -> None:
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

        assert result.success is True
        assert (output_dir / "colors.json").read_text() == "dummy"
        assert any(p.name == "colors.json" for p in result.output_files)

    def test_inner_command_argv_is_accepted_by_cli(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        mock_processor.process_generate.return_value = _make_result()
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.create_local_processor",
            lambda *a, **kw: mock_processor,
        )
        monkeypatch.setattr(
            "color_scheme_generator.cli.main.create_container_processor",
            lambda *a, **kw: mock_processor,
        )

        processor.process_generate(request, settings)

        command = _run_call_args(processor)["command"]
        assert isinstance(command, list)
        cli_argv = command[1:]

        runner = CliRunner()
        result = runner.invoke(app, cli_argv)

        assert result.exit_code == 0, (
            f"Adapter argv rejected by live CLI\n  argv: {cli_argv}\n  stderr: {result.stderr}"
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
    def test_show_mounts_only_three_without_output_dir(self, tmp_path: Path) -> None:
        tdir = tmp_path / "templates"
        tdir.mkdir()
        img = tmp_path / "img.png"
        img.write_text("dummy")
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        fake_runtime = _FakeContainerRuntime(
            run_result=_FakeRunResult(
                stdout=json.dumps(
                    {
                        "background": {"hex": "#000000", "rgb": [0, 0, 0]},
                        "foreground": {"hex": "#ffffff", "rgb": [255, 255, 255]},
                        "cursor": {"hex": "#00ff00", "rgb": [0, 255, 0]},
                        "colors": [{"hex": "#000000", "rgb": [0, 0, 0]} for _ in range(16)],
                        "source_image": "/input/wallpaper.png",
                        "backend": "custom",
                        "generated_at": "2024-01-01T00:00:00",
                    }
                )
            )
        )

        processor = ContainerProcessor(
            fake_runtime, default_settings_path=tmp_path / "settings.toml"
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
        mounts = _run_call_args(processor)["mounts"]
        assert isinstance(mounts, list)
        assert len(mounts) == 3
        mount_by_target = {m.target: m for m in mounts}
        assert set(mount_by_target) == {
            PurePosixPath("/input"),
            PurePosixPath("/csg-config/settings.toml"),
            PurePosixPath("/templates"),
        }
        assert PurePosixPath("/output") not in mount_by_target
        assert mount_by_target[PurePosixPath("/input")].source == img.resolve().parent
        assert mount_by_target[PurePosixPath("/input")].read_only is True
        assert mount_by_target[PurePosixPath("/csg-config/settings.toml")].read_only is True
        templates_mount = mount_by_target[PurePosixPath("/templates")]
        assert templates_mount.source == tmp_path / "defaults" / "templates"

    def test_show_inner_command_has_no_runtime_flag(self, tmp_path: Path) -> None:
        tdir = tmp_path / "templates"
        tdir.mkdir()
        img = tmp_path / "img.png"
        img.write_text("dummy")
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        fake_runtime = _FakeContainerRuntime(run_result=_FakeRunResult(stdout="{}"))
        processor = ContainerProcessor(
            fake_runtime, default_settings_path=tmp_path / "settings.toml"
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

        command = _run_call_args(processor)["command"]
        assert isinstance(command, list)
        assert "--runtime" not in command
        assert command[0] == "csg"
        assert command[1] == "show"

    def test_show_runs_use_expected_environment(self, tmp_path: Path) -> None:
        tdir = tmp_path / "templates"
        tdir.mkdir()
        img = tmp_path / "img.png"
        img.write_text("dummy")
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        fake_runtime = _FakeContainerRuntime(run_result=_FakeRunResult(stdout="{}"))
        processor = ContainerProcessor(
            fake_runtime, default_settings_path=tmp_path / "settings.toml"
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

        environment = _run_call_args(processor)["environment"]
        assert environment == _CONTAINER_ENV

    def test_show_inner_command_argv_is_accepted_by_cli(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typer.testing import CliRunner

        from color_scheme_generator.cli.main import app

        templates_dir, output_dir, processor = _setup_test_env(tmp_path)
        settings = _make_settings()
        request = GenerationRequest(
            image_path=tmp_path / "input" / "wallpaper.png",
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=(),
                output_dir=output_dir,
            ),
        )

        mock_processor = MagicMock()
        mock_processor.process_show.return_value = _make_result()
        monkeypatch.setattr(
            "color_scheme_generator.cli._helpers.create_local_processor",
            lambda *a, **kw: mock_processor,
        )
        monkeypatch.setattr(
            "color_scheme_generator.cli._helpers.create_container_processor",
            lambda *a, **kw: mock_processor,
        )

        processor.process_show(request, settings)

        command = _run_call_args(processor)["command"]
        assert isinstance(command, list)
        cli_argv = command[1:]

        runner = CliRunner()
        result = runner.invoke(app, cli_argv)

        assert result.exit_code == 0, (
            f"Adapter show argv rejected by live CLI\n  argv: {cli_argv}\n  stderr: {result.stderr}"
        )


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
        return ContainerProcessor(_FakeContainerRuntime())

    def test_parses_backend_as_enum(self) -> None:
        raw = json.dumps(
            {
                "background": {"hex": "#000000", "rgb": [0, 0, 0]},
                "foreground": {"hex": "#ffffff", "rgb": [255, 255, 255]},
                "cursor": {"hex": "#00ff00", "rgb": [0, 255, 0]},
                "colors": [{"hex": "#000000", "rgb": [0, 0, 0]}] * 16,
                "source_image": "/input/test.jpg",
                "backend": "pywal",
                "generated_at": "2024-01-01T00:00:00",
            }
        )
        processor = self._make_processor()
        cs = processor._parse_color_scheme_from_json(raw)
        assert cs is not None
        assert isinstance(cs.backend, Backend)
        assert cs.backend == Backend.PYWAL

    def test_parses_generated_at_as_datetime(self) -> None:
        raw = json.dumps(
            {
                "background": {"hex": "#000000", "rgb": [0, 0, 0]},
                "foreground": {"hex": "#ffffff", "rgb": [255, 255, 255]},
                "cursor": {"hex": "#00ff00", "rgb": [0, 255, 0]},
                "colors": [{"hex": "#000000", "rgb": [0, 0, 0]}] * 16,
                "source_image": "/input/test.jpg",
                "backend": "pywal",
                "generated_at": "2024-01-01T00:00:00",
            }
        )
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
        raw = json.dumps(
            {
                "background": {"hex": "#000000", "rgb": [0, 0, 0]},
                "foreground": {"hex": "#ffffff", "rgb": [255, 255, 255]},
                "cursor": {"hex": "#00ff00", "rgb": [0, 255, 0]},
                "colors": [{"hex": "#000000", "rgb": [0, 0, 0]}] * 16,
                "source_image": "/input/test.jpg",
                "generated_at": "2024-01-01T00:00:00",
            }
        )
        processor = self._make_processor()
        assert processor._parse_color_scheme_from_json(raw) is None

    def test_returns_none_for_invalid_backend_enum(self) -> None:
        raw = json.dumps(
            {
                "background": {"hex": "#000000", "rgb": [0, 0, 0]},
                "foreground": {"hex": "#ffffff", "rgb": [255, 255, 255]},
                "cursor": {"hex": "#00ff00", "rgb": [0, 255, 0]},
                "colors": [{"hex": "#000000", "rgb": [0, 0, 0]}] * 16,
                "source_image": "/input/test.jpg",
                "backend": "nonexistent_backend",
                "generated_at": "2024-01-01T00:00:00",
            }
        )
        processor = self._make_processor()
        assert processor._parse_color_scheme_from_json(raw) is None
