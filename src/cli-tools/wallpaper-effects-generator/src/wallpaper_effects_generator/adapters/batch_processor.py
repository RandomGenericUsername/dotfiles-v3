from __future__ import annotations

import signal
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any

from wallpaper_effects_generator.domain.enums import ItemType
from wallpaper_effects_generator.domain.exceptions import (
    BatchProcessingError,
    CompositeNotFoundError,
    EffectNotFoundError,
    NoInputFilesError,
    PresetNotFoundError,
)
from wallpaper_effects_generator.domain.models import (
    BatchRequest,
    BatchResult,
    EffectsCatalog,
    ProcessingRequest,
    ProcessingResult,
)
from wallpaper_effects_generator.domain.services import OutputPathService
from wallpaper_effects_generator.ports.processor import EffectProcessorPort

_ALL_EXPANSION: tuple[ItemType, ...] = (ItemType.EFFECT, ItemType.COMPOSITE, ItemType.PRESET)


class BatchProcessor:
    def __init__(
        self,
        single_processor: EffectProcessorPort,
        catalog: EffectsCatalog,
        output_path_service: OutputPathService | None = None,
    ) -> None:
        self._processor = single_processor
        self._catalog = catalog
        self._output_path_service = output_path_service or OutputPathService()

    def process_batch(self, request: BatchRequest) -> BatchResult:
        input_path = request.input_path
        if not input_path.exists() or not input_path.is_file():
            raise NoInputFilesError(str(input_path))

        items = self._enumerate_items(request.item_types)
        if not items:
            return BatchResult(
                total=0,
                succeeded=0,
                failed=0,
                attempted=0,
                results=(),
                output_dir=request.output_dir,
            )

        output_dir = self._output_path_service.batch_output_dir(
            input_path=input_path,
            output_dir=request.output_dir,
            flat=request.flat,
            explicit_output=request.explicit_output,
        )
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise BatchProcessingError(f"Failed to create output directory {output_dir}: {e}")

        request_with_output = BatchRequest(
            input_path=input_path,
            output_dir=output_dir,
            item_types=request.item_types,
            flat=request.flat,
            explicit_output=request.explicit_output,
            parallel=request.parallel,
            strict=request.strict,
            max_workers=request.max_workers,
            params=request.params,
        )

        if request.parallel:
            return self._process_parallel(request_with_output, items)
        return self._process_sequential(request_with_output, items)

    def _enumerate_items(self, item_types: tuple[ItemType, ...]) -> list[tuple[ItemType, str]]:
        expanded: list[ItemType] = []
        for t in item_types:
            if t is ItemType.ALL:
                expanded.extend(_ALL_EXPANSION)
            else:
                expanded.append(t)

        items: list[tuple[ItemType, str]] = []
        seen: set[tuple[ItemType, str]] = set()
        for t in expanded:
            names = self._get_names_for_type(t)
            for name in names:
                key = (t, name)
                if key not in seen:
                    seen.add(key)
                    items.append(key)
        return items

    def _get_names_for_type(self, item_type: ItemType) -> list[str]:
        if item_type == ItemType.EFFECT:
            return [e.name for e in self._catalog.effects]
        if item_type == ItemType.COMPOSITE:
            return [c.name for c in self._catalog.composites]
        if item_type == ItemType.PRESET:
            return [p.name for p in self._catalog.presets]
        return []

    def _process_sequential(
        self, request: BatchRequest, items: list[tuple[ItemType, str]]
    ) -> BatchResult:
        results: list[ProcessingResult] = []
        succeeded = 0
        failed = 0
        cancelled = 0

        for item_type, name in items:
            try:
                result = self._process_one(item_type, name, request)
                results.append(result)
                if result.success:
                    succeeded += 1
                else:
                    failed += 1
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                failed += 1
                results.append(
                    ProcessingResult(
                        success=False,
                        command="",
                        stdout="",
                        stderr=str(e),
                        return_code=-1,
                        duration=0.0,
                    )
                )
            if request.strict and failed > 0:
                cancelled = len(items) - (succeeded + failed)
                break

        return BatchResult(
            total=len(items),
            succeeded=succeeded,
            failed=failed,
            attempted=succeeded + failed,
            cancelled=cancelled,
            results=tuple(results),
            output_dir=request.output_dir,
        )

    def _process_parallel(
        self, request: BatchRequest, items: list[tuple[ItemType, str]]
    ) -> BatchResult:
        results: list[ProcessingResult] = []
        succeeded = 0
        failed = 0
        interrupted = False

        original: Any = None
        if threading.current_thread() is threading.main_thread():

            def handler(signum: int, frame: Any) -> None:
                nonlocal interrupted
                interrupted = True
                if callable(original):
                    original(signum, frame)

            original = signal.signal(signal.SIGINT, handler)

        cancelled = 0
        try:
            with ThreadPoolExecutor(max_workers=request.max_workers or None) as executor:
                future_map = {
                    executor.submit(self._process_one, item_type, name, request): (item_type, name)
                    for item_type, name in items
                }
                pending = set(future_map.keys())

                while pending:
                    if interrupted or (request.strict and failed > 0):
                        executor.shutdown(wait=False, cancel_futures=True)
                        for f in pending:
                            if f.cancel():
                                cancelled += 1
                        # Drain outcomes from futures not cancelled (done at break time,
                        # or still running) so total == succeeded + failed + cancelled.
                        for f in pending:
                            if f.cancelled():
                                continue
                            try:
                                result = f.result()
                                results.append(result)
                                if result.success:
                                    succeeded += 1
                                else:
                                    failed += 1
                            except (KeyboardInterrupt, SystemExit):
                                raise
                            except Exception as e:
                                failed += 1
                                results.append(
                                    ProcessingResult(
                                        success=False,
                                        command="",
                                        stdout="",
                                        stderr=str(e),
                                        return_code=-1,
                                        duration=0.0,
                                    )
                                )
                        break
                    done, pending = wait(pending, return_when=FIRST_COMPLETED, timeout=0.5)
                    for future in done:
                        item = future_map[future]
                        try:
                            result = future.result()
                            results.append(result)
                            if result.success:
                                succeeded += 1
                            else:
                                failed += 1
                        except (KeyboardInterrupt, SystemExit):
                            raise
                        except Exception as e:
                            failed += 1
                            results.append(
                                ProcessingResult(
                                    success=False,
                                    command="",
                                    stdout="",
                                    stderr=str(e),
                                    return_code=-1,
                                    duration=0.0,
                                )
                            )
        finally:
            if original is not None:
                signal.signal(signal.SIGINT, original)

        return BatchResult(
            total=len(items),
            succeeded=succeeded,
            failed=failed,
            attempted=succeeded + failed,
            cancelled=cancelled,
            results=tuple(results),
            output_dir=request.output_dir,
        )

    def _process_one(
        self,
        item_type: ItemType,
        name: str,
        request: BatchRequest,
    ) -> ProcessingResult:
        output_path = self._output_path_service.resolve(
            input_path=request.input_path,
            output_dir=request.output_dir,
            item_type=item_type,
            flat=request.flat,
            explicit_output=request.explicit_output,
            output_name=name,
        )

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            processing_request = ProcessingRequest(
                input_path=request.input_path,
                output_path=output_path,
            )
            params = dict(request.params) if request.params else None
            if item_type == ItemType.EFFECT:
                return self._processor.process_effect(name, processing_request, params)
            if item_type == ItemType.COMPOSITE:
                return self._processor.process_composite(name, processing_request, params)
            if item_type == ItemType.PRESET:
                return self._processor.process_preset(name, processing_request, params)
            return ProcessingResult(
                success=False,
                command="",
                stdout="",
                stderr=f"Unknown item type: {item_type}",
                return_code=-1,
                duration=0.0,
                output_path=output_path,
            )
        except (EffectNotFoundError, CompositeNotFoundError, PresetNotFoundError) as e:
            return ProcessingResult(
                success=False,
                command="",
                stdout="",
                stderr=str(e),
                return_code=-1,
                duration=0.0,
                output_path=output_path,
            )
        except OSError as e:
            return ProcessingResult(
                success=False,
                command="",
                stdout="",
                stderr=str(e),
                return_code=-1,
                duration=0.0,
                output_path=output_path,
            )
