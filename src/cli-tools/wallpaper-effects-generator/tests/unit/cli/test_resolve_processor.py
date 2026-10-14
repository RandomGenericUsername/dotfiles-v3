"""`_resolve_processor` must select the processor from `settings.runtime.mode`.

Regression: container mode was unreachable for real runs (the container
processor was only returned for `--dry-run`), so `weg batch all` always ran
the host-local `magick` even when settings said `mode = "container"`.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from wallpaper_effects_generator.adapters.container_processor import ContainerProcessor
from wallpaper_effects_generator.adapters.dry_run_processor import DryRunProcessor
from wallpaper_effects_generator.adapters.local_processor import LocalProcessor
from wallpaper_effects_generator.cli import process as process_mod
from wallpaper_effects_generator.domain.enums import RuntimeMode
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    ContainerSettings,
    EffectsCatalog,
    ProcessingSettings,
    RuntimeSettings,
)


def _settings(mode: RuntimeMode, temp_dir: Path | None = None) -> AppSettings:
    return AppSettings(
        runtime=RuntimeSettings(mode=mode),
        container=ContainerSettings(engine="podman"),
        processing=ProcessingSettings(temp_dir=temp_dir),
    )


def test_container_mode_selects_container_processor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_mod, "create_container_engine", lambda cs: Mock())
    processor = process_mod._resolve_processor(
        _settings(RuntimeMode.CONTAINER), EffectsCatalog(), Path("/tmp")
    )
    assert isinstance(processor, ContainerProcessor)


def test_local_mode_selects_local_processor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_mod, "create_command_runner", lambda s: Mock())
    processor = process_mod._resolve_processor(
        _settings(RuntimeMode.LOCAL), EffectsCatalog(), Path("/tmp")
    )
    assert isinstance(processor, LocalProcessor)


def test_dry_run_selects_dry_run_processor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_mod, "create_command_runner", lambda s: Mock())
    processor = process_mod._resolve_processor(
        _settings(RuntimeMode.LOCAL), EffectsCatalog(), Path("/tmp"), dry_run=True
    )
    assert isinstance(processor, DryRunProcessor)


def test_local_processor_receives_settings_temp_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_mod, "create_command_runner", lambda s: Mock())
    temp_dir = Path("/tmp/weg-configured-tmp")
    processor = process_mod._resolve_processor(
        _settings(RuntimeMode.LOCAL, temp_dir=temp_dir), EffectsCatalog(), Path("/tmp")
    )
    assert isinstance(processor, LocalProcessor)
    assert processor._temp_dir == temp_dir


def test_container_processor_uses_container_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel_engine = Mock()
    monkeypatch.setattr(process_mod, "create_container_engine", lambda cs: sentinel_engine)
    processor = process_mod._resolve_processor(
        _settings(RuntimeMode.CONTAINER), EffectsCatalog(), Path("/tmp")
    )
    assert isinstance(processor, ContainerProcessor)
    assert processor._get_engine() is sentinel_engine
