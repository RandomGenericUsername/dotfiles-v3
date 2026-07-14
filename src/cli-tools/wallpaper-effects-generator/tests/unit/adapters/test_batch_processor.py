from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from wallpaper_effects_generator.adapters.batch_processor import BatchProcessor
from wallpaper_effects_generator.domain.enums import ItemType
from wallpaper_effects_generator.domain.exceptions import NoInputFilesError
from wallpaper_effects_generator.domain.models import (
    BatchRequest,
    EffectsCatalog,
    ProcessingResult,
)
from wallpaper_effects_generator.domain.services import OutputPathService


def _make_success_processor() -> MagicMock:
    mock = MagicMock()
    mock.process_effect.return_value = ProcessingResult(
        success=True,
        command="magick input.png effect output.png",
        stdout="",
        stderr="",
        return_code=0,
        duration=1.0,
    )
    mock.process_composite.return_value = ProcessingResult(
        success=True,
        command="magick input.png composite output.png",
        stdout="",
        stderr="",
        return_code=0,
        duration=1.0,
    )
    mock.process_preset.return_value = ProcessingResult(
        success=True,
        command="magick input.png preset output.png",
        stdout="",
        stderr="",
        return_code=0,
        duration=1.0,
    )
    return mock


def _make_partial_processor() -> MagicMock:
    mock = MagicMock()

    def effect_side_effect(name: str, request: object, params: dict | None = None) -> ProcessingResult:
        if name == "blur":
            return ProcessingResult(
                success=True,
                command="effect ok",
                stdout="",
                stderr="",
                return_code=0,
                duration=1.0,
            )
        return ProcessingResult(
            success=False,
            command="effect fail",
            stdout="",
            stderr="error",
            return_code=1,
            duration=1.0,
        )

    mock.process_effect = MagicMock(side_effect=effect_side_effect)
    mock.process_composite.return_value = ProcessingResult(
        success=True,
        command="composite ok",
        stdout="",
        stderr="",
        return_code=0,
        duration=1.0,
    )
    mock.process_preset.return_value = ProcessingResult(
        success=True,
        command="preset ok",
        stdout="",
        stderr="",
        return_code=0,
        duration=1.0,
    )
    return mock


def _make_all_fail_processor() -> MagicMock:
    mock = MagicMock()
    mock.process_effect.return_value = ProcessingResult(
        success=False,
        command="fail",
        stdout="",
        stderr="error",
        return_code=1,
        duration=1.0,
    )
    mock.process_composite.return_value = ProcessingResult(
        success=False,
        command="fail",
        stdout="",
        stderr="error",
        return_code=1,
        duration=1.0,
    )
    mock.process_preset.return_value = ProcessingResult(
        success=False,
        command="fail",
        stdout="",
        stderr="error",
        return_code=1,
        duration=1.0,
    )
    return mock


def _make_empty_catalog() -> EffectsCatalog:
    return EffectsCatalog(effects=(), composites=(), presets=())


def _make_full_catalog() -> EffectsCatalog:
    return EffectsCatalog(
        effects=(
            _make_mock_with_name("blur"),
            _make_mock_with_name("sharpen"),
        ),
        composites=(
            _make_mock_with_name("blur-resize"),
        ),
        presets=(
            _make_mock_with_name("social"),
        ),
    )


def _make_mock_with_name(name: str) -> MagicMock:
    m = MagicMock()
    m.name = name
    return m


def _catalog_with_effects(*names: str) -> EffectsCatalog:
    return EffectsCatalog(
        effects=tuple(_make_mock_with_name(n) for n in names),
        composites=(),
        presets=(),
    )


class TestBatchProcessor:
    """Unit tests for BatchProcessor."""

    def _make_batch_processor(
        self,
        processor: MagicMock | None = None,
        catalog: EffectsCatalog | None = None,
    ) -> BatchProcessor:
        return BatchProcessor(
            single_processor=processor or _make_success_processor(),
            catalog=catalog or _make_full_catalog(),
        )

    def test_all_effects_processed_when_scope_effects(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        catalog = _catalog_with_effects("blur", "sharpen")

        mock_processor = _make_success_processor()
        bp = self._make_batch_processor(processor=mock_processor, catalog=catalog)

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.EFFECT,),
        )
        result = bp.process_batch(request)

        assert result.total == 2
        assert result.succeeded == 2
        assert result.failed == 0
        assert mock_processor.process_effect.call_count == 2

    def test_all_composites_processed_when_scope_composites(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        catalog = EffectsCatalog(
            effects=(),
            composites=(_make_mock_with_name("blur-resize"),),
            presets=(),
        )

        mock_processor = _make_success_processor()
        bp = self._make_batch_processor(processor=mock_processor, catalog=catalog)

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.COMPOSITE,),
        )
        result = bp.process_batch(request)

        assert result.total == 1
        assert result.succeeded == 1
        assert mock_processor.process_composite.call_count == 1

    def test_all_presets_processed_when_scope_presets(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        catalog = EffectsCatalog(
            effects=(),
            composites=(),
            presets=(_make_mock_with_name("social"),),
        )

        mock_processor = _make_success_processor()
        bp = self._make_batch_processor(processor=mock_processor, catalog=catalog)

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.PRESET,),
        )
        result = bp.process_batch(request)

        assert result.total == 1
        assert result.succeeded == 1
        assert mock_processor.process_preset.call_count == 1

    def test_all_expands_to_effects_composites_presets(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")

        mock_processor = _make_success_processor()
        bp = self._make_batch_processor(processor=mock_processor)

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.ALL,),
        )
        result = bp.process_batch(request)

        assert result.total == 4  # 2 effects + 1 composite + 1 preset
        assert result.succeeded == 4
        assert mock_processor.process_effect.call_count == 2
        assert mock_processor.process_composite.call_count == 1
        assert mock_processor.process_preset.call_count == 1

    def test_partial_failure_returns_mixed_outcomes(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        catalog = _catalog_with_effects("blur", "sharpen")

        mock_processor = _make_partial_processor()
        bp = self._make_batch_processor(processor=mock_processor, catalog=catalog)

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.EFFECT,),
        )
        result = bp.process_batch(request)

        assert result.total == 2
        assert result.succeeded == 1
        assert result.failed == 1
        assert len(result.results) == 2

    def test_total_failure_returns_valid_batch_result(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        catalog = _catalog_with_effects("blur")

        mock_processor = _make_all_fail_processor()
        bp = self._make_batch_processor(processor=mock_processor, catalog=catalog)

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.EFFECT,),
        )
        result = bp.process_batch(request)

        assert result.total == 1
        assert result.succeeded == 0
        assert result.failed == 1
        assert len(result.results) == 1

    def test_strict_mode_stops_on_first_failure(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        catalog = _catalog_with_effects("blur", "sharpen", "edge")

        mock_processor = _make_partial_processor()
        bp = self._make_batch_processor(processor=mock_processor, catalog=catalog)

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.EFFECT,),
            strict=True,
            parallel=False,
        )
        result = bp.process_batch(request)

        assert result.total == 3
        assert result.succeeded == 1
        assert result.failed == 1
        assert result.cancelled == 1  # strict skipped remaining items
        assert len(result.results) == 2

    def test_strict_parallel_cancels_remaining(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        catalog = _catalog_with_effects("blur", "sharpen", "edge")

        mock_processor = _make_partial_processor()
        bp = self._make_batch_processor(processor=mock_processor, catalog=catalog)

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.EFFECT,),
            strict=True,
            parallel=True,
            max_workers=2,
        )
        result = bp.process_batch(request)

        assert result.succeeded >= 1
        assert result.failed >= 1
        assert result.total == result.succeeded + result.failed + result.cancelled

    def test_strict_parallel_drains_inflight_futures_after_break(self, tmp_path: Path) -> None:
        """Strict-parallel break drains in-flight futures so the accounting
        invariant total == succeeded + failed + cancelled holds even when
        items were still running at break time."""
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        catalog = _catalog_with_effects("slow", "fail")

        blocker_release = threading.Event()
        slow_started = threading.Event()

        def side_effect(name: str, request: object, params: dict | None = None) -> ProcessingResult:
            if name == "slow":
                slow_started.set()
                blocker_release.wait(timeout=2.0)  # blocked at break time
                return ProcessingResult(
                    success=True,
                    command="slow-ok",
                    stdout="",
                    stderr="",
                    return_code=0,
                    duration=0.1,
                )
            # "fail" — wait until "slow" is in-flight, then return failure
            slow_started.wait(timeout=2.0)
            return ProcessingResult(
                success=False,
                command="fail",
                stdout="",
                stderr="err",
                return_code=1,
                duration=0.0,
            )

        mock_processor = MagicMock()
        mock_processor.process_effect = MagicMock(side_effect=side_effect)
        bp = self._make_batch_processor(processor=mock_processor, catalog=catalog)

        # Release the blocker shortly so the drain's f.result() can complete
        threading.Timer(0.2, blocker_release.set).start()

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.EFFECT,),
            strict=True,
            parallel=True,
            max_workers=2,
        )
        result = bp.process_batch(request)

        # "slow" must be drained — its outcome counted even though it was
        # still running when strict break fired. Without the drain patch,
        # succeeded would be 0 and the invariant would break.
        assert result.total == 2
        assert result.failed == 1
        assert result.succeeded == 1  # "slow" drained, not lost
        assert result.cancelled == 0
        assert result.total == result.succeeded + result.failed + result.cancelled

    def test_parallel_mode_executes_with_max_workers(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")

        mock_processor = _make_success_processor()
        bp = self._make_batch_processor(processor=mock_processor)

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.EFFECT,),
            parallel=True,
            max_workers=2,
        )
        result = bp.process_batch(request)

        assert result.total == 2
        assert result.succeeded == 2
        assert mock_processor.process_effect.call_count == 2

    def test_empty_catalog_returns_batch_result_with_total_zero(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")

        mock_processor = _make_success_processor()
        bp = self._make_batch_processor(
            processor=mock_processor, catalog=_make_empty_catalog()
        )

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.EFFECT,),
        )
        result = bp.process_batch(request)

        assert result.total == 0
        assert result.succeeded == 0
        assert result.failed == 0

    def test_sequential_mode_executes_in_order(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        catalog = _catalog_with_effects("blur", "sharpen", "edge")

        mock = MagicMock()
        processed: list[str] = []

        def track(name: str, request: object, params: dict | None = None) -> ProcessingResult:
            processed.append(name)
            return ProcessingResult(
                success=True,
                command=f"magick {name}",
                stdout="",
                stderr="",
                return_code=0,
                duration=0.5,
            )

        mock.process_effect.side_effect = track
        bp = self._make_batch_processor(processor=mock, catalog=catalog)

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.EFFECT,),
            parallel=False,
        )
        result = bp.process_batch(request)

        assert processed == ["blur", "sharpen", "edge"]
        assert result.total == 3
        assert result.succeeded == 3
        assert all(r.success for r in result.results)

    def test_non_strict_continues_on_failure(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        catalog = _catalog_with_effects("blur", "sharpen", "edge")

        mock_processor = _make_partial_processor()
        bp = self._make_batch_processor(processor=mock_processor, catalog=catalog)

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.EFFECT,),
            strict=False,
            parallel=False,
        )
        result = bp.process_batch(request)

        assert result.total == 3
        assert len(result.results) == 3
        assert result.succeeded == 1
        assert result.failed == 2
        assert result.cancelled == 0

    def test_strict_parallel_no_cancelled_if_no_failure(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        catalog = _catalog_with_effects("blur", "sharpen", "edge")

        mock_processor = _make_success_processor()
        bp = self._make_batch_processor(processor=mock_processor, catalog=catalog)

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(ItemType.EFFECT,),
            strict=True,
            parallel=True,
            max_workers=2,
        )
        result = bp.process_batch(request)

        assert result.total == 3
        assert result.succeeded == 3
        assert result.failed == 0
        assert result.cancelled == 0

    def test_input_path_does_not_exist_raises_error(self, tmp_path: Path) -> None:
        bp = self._make_batch_processor()

        request = BatchRequest(
            input_path=tmp_path / "nonexistent.png",
            output_dir=tmp_path,
            item_types=(ItemType.EFFECT,),
        )
        with pytest.raises(NoInputFilesError):
            bp.process_batch(request)

    def test_empty_item_types_returns_zero_batch_result(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.png"
        input_file.write_text("dummy")
        bp = self._make_batch_processor()

        request = BatchRequest(
            input_path=input_file,
            output_dir=tmp_path,
            item_types=(),
        )
        result = bp.process_batch(request)

        assert result.total == 0
        assert result.succeeded == 0
        assert result.failed == 0

    def test_directory_input_path_raises_error(self, tmp_path: Path) -> None:
        bp = self._make_batch_processor()

        request = BatchRequest(
            input_path=tmp_path,
            output_dir=tmp_path,
            item_types=(ItemType.EFFECT,),
        )
        with pytest.raises(NoInputFilesError):
            bp.process_batch(request)
