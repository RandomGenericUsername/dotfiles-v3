from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from wallpaper_effects_generator.cli.main import app
from wallpaper_effects_generator.domain.models import ProcessingResult

runner = CliRunner()


def _make_mock_processor() -> MagicMock:
    mock = MagicMock()
    mock.process_effect.return_value = ProcessingResult(
        success=True,
        command="magick input.png -blur 0x8 output.png",
        stdout="",
        stderr="",
        return_code=0,
    )
    mock.process_composite.return_value = ProcessingResult(
        success=True,
        command="magick ...",
        stdout="",
        stderr="",
        return_code=0,
    )
    mock.process_preset.return_value = ProcessingResult(
        success=True,
        command="magick ...",
        stdout="",
        stderr="",
        return_code=0,
    )
    return mock


class TestProcessEffectCommand:
    @staticmethod
    def _mock_context(*args: Any, **kwargs: Any) -> tuple[MagicMock, MagicMock]:
        return (MagicMock(), MagicMock())

    def test_effect_dry_run(self) -> None:
        mock_processor = _make_mock_processor()
        with (
            patch(
                "wallpaper_effects_generator.cli.process._resolve_processor",
                return_value=mock_processor,
            ),
            patch(
                "wallpaper_effects_generator.cli.process._resolve_context",
                self._mock_context,
            ),
            patch("wallpaper_effects_generator.cli.process.Path.exists", return_value=True),
        ):
            result = runner.invoke(
                app,
                [
                    "process",
                    "effect",
                    "blur",
                    "/tmp/test.png",
                    "--dry-run",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"

    def test_effect_with_param(self) -> None:
        mock_processor = _make_mock_processor()
        with (
            patch(
                "wallpaper_effects_generator.cli.process._resolve_processor",
                return_value=mock_processor,
            ),
            patch(
                "wallpaper_effects_generator.cli.process._resolve_context",
                self._mock_context,
            ),
            patch("wallpaper_effects_generator.cli.process.Path.exists", return_value=True),
        ):
            result = runner.invoke(
                app,
                [
                    "process",
                    "effect",
                    "blur",
                    "/tmp/test.png",
                    "--param",
                    "radius=0x8",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


class TestProcessCompositeCommand:
    def test_composite_dry_run(self) -> None:
        mock_processor = _make_mock_processor()
        with (
            patch(
                "wallpaper_effects_generator.cli.process._resolve_processor",
                return_value=mock_processor,
            ),
            patch(
                "wallpaper_effects_generator.cli.process._resolve_context",
                TestProcessEffectCommand._mock_context,
            ),
            patch("wallpaper_effects_generator.cli.process.Path.exists", return_value=True),
        ):
            result = runner.invoke(
                app,
                [
                    "process",
                    "composite",
                    "blur-resize",
                    "/tmp/test.png",
                    "--dry-run",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


class TestProcessPresetCommand:
    def test_preset_dry_run(self) -> None:
        mock_processor = _make_mock_processor()
        with (
            patch(
                "wallpaper_effects_generator.cli.process._resolve_processor",
                return_value=mock_processor,
            ),
            patch(
                "wallpaper_effects_generator.cli.process._resolve_context",
                TestProcessEffectCommand._mock_context,
            ),
            patch("wallpaper_effects_generator.cli.process.Path.exists", return_value=True),
        ):
            result = runner.invoke(
                app,
                [
                    "process",
                    "preset",
                    "social",
                    "/tmp/test.png",
                    "--dry-run",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


def test_process_effect_json_output(tmp_path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text('version = "1.0"\n')
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text('version: "1.0"\n')

    mock_processor = _make_mock_processor()
    with (
        patch(
            "wallpaper_effects_generator.cli.process._resolve_processor",
            return_value=mock_processor,
        ),
        patch(
            "wallpaper_effects_generator.cli.process._resolve_context",
            TestProcessEffectCommand._mock_context,
        ),
        patch("wallpaper_effects_generator.cli.process.Path.exists", return_value=True),
    ):
        result = runner.invoke(
            app,
            [
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "--output-format",
                "json",
                "process",
                "effect",
                "blur",
                "/tmp/test.png",
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


class TestContainerEngineFlag:
    def test_container_engine_docker(self) -> None:
        mock_processor = _make_mock_processor()
        with (
            patch(
                "wallpaper_effects_generator.cli.process._resolve_processor",
                return_value=mock_processor,
            ),
            patch(
                "wallpaper_effects_generator.cli.process._resolve_context",
                TestProcessEffectCommand._mock_context,
            ),
            patch("wallpaper_effects_generator.cli.process.Path.exists", return_value=True),
        ):
            result = runner.invoke(
                app,
                [
                    "--container-engine",
                    "docker",
                    "process",
                    "effect",
                    "blur",
                    "/tmp/test.png",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"

    def test_container_engine_podman(self) -> None:
        mock_processor = _make_mock_processor()
        with (
            patch(
                "wallpaper_effects_generator.cli.process._resolve_processor",
                return_value=mock_processor,
            ),
            patch(
                "wallpaper_effects_generator.cli.process._resolve_context",
                TestProcessEffectCommand._mock_context,
            ),
            patch("wallpaper_effects_generator.cli.process.Path.exists", return_value=True),
        ):
            result = runner.invoke(
                app,
                [
                    "--container-engine",
                    "podman",
                    "process",
                    "effect",
                    "blur",
                    "/tmp/test.png",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"

    def test_invalid_container_engine(self) -> None:
        result = runner.invoke(
            app,
            [
                "--container-engine",
                "invalid",
                "process",
                "effect",
                "blur",
                "/tmp/test.png",
            ],
        )
        assert result.exit_code != 0
        output = result.stdout + result.stderr
        assert "Invalid" in output

    def test_invalid_runtime(self) -> None:
        result = runner.invoke(
            app,
            [
                "--runtime",
                "invalid",
                "process",
                "effect",
                "blur",
                "/tmp/test.png",
            ],
        )
        assert result.exit_code != 0
        output = result.stdout + result.stderr
        assert "Invalid" in output

    def test_orthogonality_local_and_container_engine(self) -> None:
        mock_processor = _make_mock_processor()
        with (
            patch(
                "wallpaper_effects_generator.cli.process._resolve_processor",
                return_value=mock_processor,
            ),
            patch(
                "wallpaper_effects_generator.cli.process._resolve_context",
                TestProcessEffectCommand._mock_context,
            ),
            patch("wallpaper_effects_generator.cli.process.Path.exists", return_value=True),
        ):
            result = runner.invoke(
                app,
                [
                    "--runtime",
                    "local",
                    "--container-engine",
                    "docker",
                    "process",
                    "effect",
                    "blur",
                    "/tmp/test.png",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


def test_process_effect_rich_output_default(tmp_path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text('version = "1.0"\n')
    effects_file = tmp_path / "effects.yaml"
    effects_file.write_text('version: "1.0"\n')

    mock_processor = _make_mock_processor()
    with (
        patch(
            "wallpaper_effects_generator.cli.process._resolve_processor",
            return_value=mock_processor,
        ),
        patch(
            "wallpaper_effects_generator.cli.process._resolve_context",
            TestProcessEffectCommand._mock_context,
        ),
        patch("wallpaper_effects_generator.cli.process.Path.exists", return_value=True),
    ):
        result = runner.invoke(
            app,
            [
                "--config",
                str(config_file),
                "--effects",
                str(effects_file),
                "--output-format",
                "rich",
                "process",
                "effect",
                "blur",
                "/tmp/test.png",
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
