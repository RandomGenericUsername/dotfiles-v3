from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from wallpaper_effects_generator.adapters.local_processor import LocalProcessor
from wallpaper_effects_generator.adapters.subprocess_runner import (
    SubprocessCommandRunner,
)
from wallpaper_effects_generator.domain.models import (
    EffectsCatalog,
    ProcessingRequest,
)


@pytest.fixture
def effects_catalog() -> EffectsCatalog:
    from wallpaper_effects_generator.domain.models import (
        EffectDefinition,
    )

    return EffectsCatalog(
        effects=(
            EffectDefinition(
                name="identity",
                description="Identity (copy input)",
                command="cp {{input}} {{output}}",
                parameters=(),
            ),
        ),
    )


@pytest.mark.skipif(
    not shutil.which("cp"),
    reason="cp binary not available",
)
def test_local_processing_with_real_command(
    tmp_path: Path, effects_catalog: EffectsCatalog
) -> None:
    runner = SubprocessCommandRunner(binary="cp")
    processor = LocalProcessor(
        command_runner=runner,
        catalog=effects_catalog,
        output_dir=tmp_path,
    )

    input_file = tmp_path / "input.png"
    input_file.write_text("dummy content")

    request = ProcessingRequest(
        input_path=input_file,
        output_path=tmp_path / "output.png",
    )

    result = processor.process_effect("identity", request)
    assert result.success
    assert result.return_code == 0
    output_file = tmp_path / "effect" / "input.png"
    if not output_file.exists():
        output_file = tmp_path / "input.png"
    assert result.output_path is not None
