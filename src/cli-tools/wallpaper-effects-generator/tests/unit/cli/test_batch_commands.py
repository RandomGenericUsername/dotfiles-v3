from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from wallpaper_effects_generator.cli.main import app
from wallpaper_effects_generator.domain.models import BatchResult, ProcessingResult

runner = CliRunner()


def _mock_batch_result(
    total: int = 2,
    succeeded: int = 2,
    failed: int = 0,
    output_dir: Path | None = None,
) -> BatchResult:
    return BatchResult(
        total=total,
        succeeded=succeeded,
        failed=failed,
        attempted=succeeded + failed,
        cancelled=0,
        results=tuple(
            ProcessingResult(
                success=True,
                command="magick ...",
                stdout="",
                stderr="",
                return_code=0,
                output_path=output_dir / f"output_{i}.png" if output_dir else None,
            )
            for i in range(succeeded)
        ) + tuple(
            ProcessingResult(
                success=False,
                command="magick ...",
                stdout="",
                stderr="error",
                return_code=1,
                output_path=output_dir / f"output_{i}.png" if output_dir else None,
            )
            for i in range(succeeded, succeeded + failed)
        ),
        output_dir=output_dir,
    )


def _mock_context(*args: Any, **kwargs: Any) -> tuple[MagicMock, MagicMock]:
    return (MagicMock(), MagicMock())


class TestBatchEffectsCommand:
    def test_batch_effects_basic(self) -> None:
        mock_bp = MagicMock()
        mock_bp.process_batch.return_value = _mock_batch_result(total=2, succeeded=2)

        with (
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_processor",
                return_value=MagicMock(),
            ),
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_context",
                _mock_context,
            ),
            patch(
                "wallpaper_effects_generator.cli.batch.create_batch_processor",
                return_value=mock_bp,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "batch",
                    "effects",
                    "/tmp/test.png",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"

    def test_batch_effects_json_output(self) -> None:
        mock_bp = MagicMock()
        mock_bp.process_batch.return_value = _mock_batch_result(total=2, succeeded=2)

        with (
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_processor",
                return_value=MagicMock(),
            ),
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_context",
                _mock_context,
            ),
            patch(
                "wallpaper_effects_generator.cli.batch.create_batch_processor",
                return_value=mock_bp,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "--output-format",
                    "json",
                    "batch",
                    "effects",
                    "/tmp/test.png",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
            data = json.loads(result.stdout)
            assert "total" in data
            assert data["total"] == 2

    def test_batch_effects_rich_output(self) -> None:
        mock_bp = MagicMock()
        mock_bp.process_batch.return_value = _mock_batch_result(total=2, succeeded=2)

        with (
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_processor",
                return_value=MagicMock(),
            ),
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_context",
                _mock_context,
            ),
            patch(
                "wallpaper_effects_generator.cli.batch.create_batch_processor",
                return_value=mock_bp,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "--output-format",
                    "rich",
                    "batch",
                    "effects",
                    "/tmp/test.png",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"

    def test_batch_effects_plain_output(self) -> None:
        mock_bp = MagicMock()
        mock_bp.process_batch.return_value = _mock_batch_result(total=2, succeeded=2)

        with (
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_processor",
                return_value=MagicMock(),
            ),
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_context",
                _mock_context,
            ),
            patch(
                "wallpaper_effects_generator.cli.batch.create_batch_processor",
                return_value=mock_bp,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "--output-format",
                    "plain",
                    "batch",
                    "effects",
                    "/tmp/test.png",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"

    def test_batch_effects_sequential_mode(self) -> None:
        mock_bp = MagicMock()
        mock_bp.process_batch.return_value = _mock_batch_result(total=2, succeeded=2)

        with (
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_processor",
                return_value=MagicMock(),
            ),
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_context",
                _mock_context,
            ),
            patch(
                "wallpaper_effects_generator.cli.batch.create_batch_processor",
                return_value=mock_bp,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "batch",
                    "effects",
                    "/tmp/test.png",
                    "--no-parallel",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
            call_kwargs = mock_bp.process_batch.call_args[0][0]
            assert call_kwargs.parallel is False

    def test_batch_effects_strict_mode(self) -> None:
        mock_bp = MagicMock()
        mock_bp.process_batch.return_value = _mock_batch_result(total=2, succeeded=1, failed=1)

        with (
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_processor",
                return_value=MagicMock(),
            ),
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_context",
                _mock_context,
            ),
            patch(
                "wallpaper_effects_generator.cli.batch.create_batch_processor",
                return_value=mock_bp,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "batch",
                    "effects",
                    "/tmp/test.png",
                    "--strict",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


class TestBatchCompositesCommand:
    def test_batch_composites_basic(self) -> None:
        mock_bp = MagicMock()
        mock_bp.process_batch.return_value = _mock_batch_result(total=1, succeeded=1)

        with (
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_processor",
                return_value=MagicMock(),
            ),
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_context",
                _mock_context,
            ),
            patch(
                "wallpaper_effects_generator.cli.batch.create_batch_processor",
                return_value=mock_bp,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "batch",
                    "composites",
                    "/tmp/test.png",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


class TestBatchPresetsCommand:
    def test_batch_presets_basic(self) -> None:
        mock_bp = MagicMock()
        mock_bp.process_batch.return_value = _mock_batch_result(total=1, succeeded=1)

        with (
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_processor",
                return_value=MagicMock(),
            ),
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_context",
                _mock_context,
            ),
            patch(
                "wallpaper_effects_generator.cli.batch.create_batch_processor",
                return_value=mock_bp,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "batch",
                    "presets",
                    "/tmp/test.png",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


class TestBatchAllCommand:
    def test_batch_all_basic(self) -> None:
        mock_bp = MagicMock()
        mock_bp.process_batch.return_value = _mock_batch_result(total=4, succeeded=4)

        with (
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_processor",
                return_value=MagicMock(),
            ),
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_context",
                _mock_context,
            ),
            patch(
                "wallpaper_effects_generator.cli.batch.create_batch_processor",
                return_value=mock_bp,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "batch",
                    "all",
                    "/tmp/test.png",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"

    def test_batch_all_json_output(self) -> None:
        mock_bp = MagicMock()
        mock_bp.process_batch.return_value = _mock_batch_result(total=4, succeeded=4)

        with (
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_processor",
                return_value=MagicMock(),
            ),
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_context",
                _mock_context,
            ),
            patch(
                "wallpaper_effects_generator.cli.batch.create_batch_processor",
                return_value=mock_bp,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "--output-format",
                    "json",
                    "batch",
                    "all",
                    "/tmp/test.png",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
            data = json.loads(result.stdout)
            assert "total" in data
            assert data["total"] == 4

    def test_batch_all_parallel_with_max_workers(self) -> None:
        mock_bp = MagicMock()
        mock_bp.process_batch.return_value = _mock_batch_result(total=4, succeeded=4)

        with (
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_processor",
                return_value=MagicMock(),
            ),
            patch(
                "wallpaper_effects_generator.cli.batch._resolve_context",
                _mock_context,
            ),
            patch(
                "wallpaper_effects_generator.cli.batch.create_batch_processor",
                return_value=mock_bp,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "batch",
                    "all",
                    "/tmp/test.png",
                    "--parallel",
                    "--max-workers",
                    "8",
                ],
            )
            assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"


def test_batch_invalid_input() -> None:
    result = runner.invoke(
        app,
        [
            "batch",
            "effects",
            "/tmp/nonexistent.png",
        ],
    )
    assert result.exit_code != 0
