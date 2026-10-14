"""`weg batch` must consume `settings.execution.*`.

`execution.parallel/strict/max_workers` are resolved settings but the CLI used
hardcoded Typer defaults, so a host's rendered settings.toml had no effect.
An explicit CLI flag must still win over the settings value.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from wallpaper_effects_generator.cli.main import app
from wallpaper_effects_generator.domain.models import BatchResult


class _CapturingBatchProcessor:
    def __init__(self) -> None:
        self.request = None

    def process_batch(self, request):
        self.request = request
        return BatchResult(total=0, output_dir=request.output_dir)


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> _CapturingBatchProcessor:
    capture = _CapturingBatchProcessor()
    monkeypatch.setattr(
        "wallpaper_effects_generator.cli.batch.create_batch_processor",
        lambda processor, catalog: capture,
    )
    return capture


def _write_config(tmp_path: Path, *, strict: bool, parallel: bool, max_workers: int) -> Path:
    config = tmp_path / "settings.toml"
    config.write_text(
        "version = '1.0'\n"
        "[execution]\n"
        f"strict = {str(strict).lower()}\n"
        f"parallel = {str(parallel).lower()}\n"
        f"max_workers = {max_workers}\n"
        "[output]\n"
        "[runtime]\n"
        "mode = 'local'\n"
        "[container]\n"
        "engine = 'docker'\n"
    )
    return config


def _write_effects(tmp_path: Path) -> Path:
    effects = tmp_path / "effects.yaml"
    effects.write_text(
        "version: '1.0'\n"
        "effects:\n"
        "  - name: blur\n"
        "    description: Blur\n"
        "    command: magick {{input}} -blur {{radius}} {{output}}\n"
    )
    return effects


def _input_file(tmp_path: Path) -> Path:
    path = tmp_path / "input.png"
    path.write_text("dummy")
    return path


def test_batch_uses_execution_settings_as_defaults(
    runner: CliRunner,
    cli_deps_with_processor,
    captured: _CapturingBatchProcessor,
    tmp_path: Path,
) -> None:
    config = _write_config(tmp_path, strict=True, parallel=False, max_workers=3)
    result = runner.invoke(
        app,
        [
            "batch",
            "--config",
            str(config),
            "--effects",
            str(_write_effects(tmp_path)),
            "effects",
            str(_input_file(tmp_path)),
            "-o",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
    assert captured.request is not None
    assert captured.request.strict is True
    assert captured.request.parallel is False
    assert captured.request.max_workers == 3


def test_batch_cli_flags_override_execution_settings(
    runner: CliRunner,
    cli_deps_with_processor,
    captured: _CapturingBatchProcessor,
    tmp_path: Path,
) -> None:
    config = _write_config(tmp_path, strict=False, parallel=True, max_workers=0)
    result = runner.invoke(
        app,
        [
            "batch",
            "--config",
            str(config),
            "--effects",
            str(_write_effects(tmp_path)),
            "effects",
            str(_input_file(tmp_path)),
            "-o",
            str(tmp_path / "out"),
            "--strict",
            "--no-parallel",
            "--max-workers",
            "7",
        ],
    )
    assert result.exit_code == 0, f"stderr: {result.stderr_bytes}"
    assert captured.request is not None
    assert captured.request.strict is True
    assert captured.request.parallel is False
    assert captured.request.max_workers == 7
