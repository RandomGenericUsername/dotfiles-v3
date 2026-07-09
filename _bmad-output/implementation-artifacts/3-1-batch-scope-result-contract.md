# Story 3.1: Batch Scope & Result Contract

Status: ready-for-dev

## Story

As a developer,
I want to batch process effects, composites, presets, or all at once,
So that I get a structured `BatchResult` with aggregate and per-item outcomes.

## Acceptance Criteria

### AC1: Batch effects enumerates and processes all effects
Given an input file and a populated effects catalog
When I run `batch effects --input <file>`
Then all effects from the catalog are enumerated and applied sequentially
And a `BatchResult` is returned with `total`, `succeeded`, `failed` counts and per-item `ProcessingResult` entries

### AC2: Batch composites and presets work identically
Given an input file and populated composites/presets
When I run `batch composites --input <file>` / `batch presets --input <file>`
Then the corresponding scope is enumerated and processed

### AC3: Batch all processes effects, composites, and presets
Given multiple scope types
When I run `batch all --input <file>`
Then effects, composites, and presets are all processed

### AC4: Partial failure returns mixed outcomes
Given some items fail during batch
When the batch completes
Then the `BatchResult` includes both succeeded and failed per-item outcomes
And the envelope shape (total/succeeded/failed) is consistent regardless of success/failure mix

### AC5: Total failure still returns a valid BatchResult
Given all items fail during batch
When the batch completes
Then a `BatchResult` is still returned with `total > 0` and `succeeded = 0`
And the envelope shape is identical to a successful batch

### AC6: JSON output renders structured BatchResult
Given `--output-format json`
When a batch command completes
Then the output is a valid JSON `BatchResult` with structured per-item details

## Tasks / Subtasks

### Domain Layer
- [ ] Add `ALL` member to existing `ItemType` enum in `domain/enums.py` (use existing EFFECT/COMPOSITE/PRESET — no new enum needed)
- [ ] Add `NoInputFilesError`, `BatchProcessingError` to `domain/exceptions.py` if not already present

### CLI Layer
- [ ] Create `cli/batch.py` — Typer subcommand group under `process` or top-level `app`
  - [ ] `app.command("batch")` with subcommands: `effects`, `composites`, `presets`, `all`
  - [ ] Common args: `--input`, `--output`, `--flat`, `--explicit-output`, `--strict`, `--parallel`, `--max-workers`, `--runtime`, `--container-engine`
  - [ ] Wire batch command context resolution via `_resolve_context` (reuse from `cli/process.py`)
  - [ ] Wire `_resolve_processor` for single-item delegation within batch loop
- [ ] Register batch subcommand in `cli/main.py` app

### Processor Layer (NEW)
- [ ] Create `adapters/batch_processor.py` — `BatchProcessor` adapter
  - [ ] Implement `EffectProcessorPort.process_batch(BatchRequest) -> BatchResult`
  - [ ] Enumerate items: if `item_types` contains `ALL`, expand to all three types
  - [ ] For each (item_type, item_name) pair, delegate to `process_effect`/`process_composite`/`process_preset`
  - [ ] Collect `ProcessingResult` per item
  - [ ] After all items, build `BatchResult(total, succeeded, failed, results, output_dir)`
  - [ ] Strict mode: stop on first failure, return partial results
  - [ ] Parallel mode: use `concurrent.futures.ThreadPoolExecutor` with `max_workers`
  - [ ] Sequential mode: loop in order
  - [ ] Handle keyboard interrupt gracefully (partial results)
  - [ ] Validate `input_path` exists before enumeration (raise `NoInputFilesError` if missing)
  - [ ] No input files matched → return `BatchResult(total=0, succeeded=0, failed=0, results=(), output_dir=...)`

### Factory Wiring
- [ ] Add `create_batch_processor(processor, settings, output_path_service) -> BatchProcessor` in `factory.py`
- [ ] Wire `CliDependencies` with optional `batch_processor` field (or compose at command site)

### Output Layer (already implemented — verify)
- [ ] Verify `JsonOutputAdapter.batch_result` exists and renders all fields
- [ ] Verify `RichOutputAdapter.batch_result` renders batch table
- [ ] Verify `PlainOutputAdapter.batch_result` renders summary + per-item lines

### Tests
- [ ] Unit tests for `ItemType.ALL` enum value and expansion logic
- [ ] Unit tests for `BatchProcessor.process_batch`:
  - [ ] All effects processed when scope=EFFECTS
  - [ ] All composites processed when scope=COMPOSITES
  - [ ] All presets processed when scope=PRESETS
  - [ ] ALL expands to effects + composites + presets
  - [ ] Partial failure returns mixed outcomes
  - [ ] Total failure returns valid BatchResult with succeeded=0
  - [ ] Strict mode stops on first failure
  - [ ] Parallel mode executes with max_workers
  - [ ] No input files → BatchResult(total=0)
  - [ ] Input path does not exist → NoInputFilesError
- [ ] CLI integration tests via `CliRunner`:
  - [ ] `batch effects --input <file>` with populated catalog
  - [ ] `batch composites --input <file>`
  - [ ] `batch presets --input <file>`
  - [ ] `batch all --input <file>`
  - [ ] `--strict` stops on failure
  - [ ] `--parallel` with --max-workers
  - [ ] `--output-format json` produces valid JSON
  - [ ] `--output-format rich` produces colored output
  - [ ] `--output-format plain` produces plain text
  - [ ] Invalid scope or missing input returns error

## Dev Notes

### Existing Batch Infrastructure (already built for you)

The domain models, ports, and output adapters are fully implemented from Epics 1. What's missing is the processor adapter and CLI command:

| Component | File | Status |
|-----------|------|--------|
| `BatchRequest` model | `domain/models.py:88-101` | DONE — all fields, frozen, validated |
| `BatchResult` model | `domain/models.py:104-110` | DONE — total/succeeded/failed/results/output_dir |
| `EffectProcessorPort.process_batch` | `ports/processor.py` | DONE — protocol method exists |
| `OutputPort.batch_result` | `ports/output.py` | DONE — protocol method exists |
| `JsonOutputAdapter.batch_result` | `adapters/output/json_output.py` | DONE — renders JSON |
| `RichOutputAdapter.batch_result` | `adapters/output/rich_output.py` | DONE — renders table |
| `PlainOutputAdapter.batch_result` | `adapters/output/plain_output.py` | DONE — renders text |
| `OutputPathService.batch_output_dir` | `domain/services.py:75-84` | DONE — resolves flat/nested paths |
| `LocalProcessor.process_batch` | `adapters/local_processor.py:196` | STUB — raises NotImplementedError |
| `DryRunProcessor.process_batch` | `adapters/dry_run_processor.py:151` | STUB — raises NotImplementedError |
| `ContainerProcessor.process_batch` | `adapters/container_processor.py:161` | STUB — raises NotImplementedError |

### Architecture Decision: Separate BatchProcessor vs Filling Stubs

The three processor stubs (`LocalProcessor`, `ContainerProcessor`, `DryRunProcessor`) each raise `NotImplementedError` for `process_batch`. The recommended approach is to create a single **`BatchProcessor`** adapter that:
- Takes an `EffectProcessorPort` (single-item processor) as a dependency
- Does NOT inherit from `EffectProcessorPort` — it's a higher-level orchestrator
- Delegates per-item processing to the injected single-item processor
- Handles enumeration, parallel/sequential dispatch, strict/non-strict control, result aggregation

This keeps the single-item processors clean and avoids duplicating batch orchestration logic across three adapters.

```python
# In adapters/batch_processor.py
class BatchProcessor:
    def __init__(
        self,
        single_processor: EffectProcessorPort,
        settings: AppSettings,
        output_path_service: OutputPathService | None = None,
    ):
        self._processor = single_processor
        self._settings = settings
        self._output_path_service = output_path_service or OutputPathService()
```

However, since `EffectProcessorPort.process_batch` is already defined on the protocol, the existing stubs should also be updated. The simplest path:
1. Create `BatchProcessor` as a standalone class (not implementing the port)
2. The CLI command creates a `BatchProcessor` wrapping the resolved single-item processor
3. The existing stub methods remain as-is (they raise NotImplementedError and that's fine since the CLI will route through `BatchProcessor`)

### Scope Enumeration Rules

From the effects catalog (`EffectsCatalog` in `domain/models.py`):
- `catalog.effects` — list of `EffectDefinition` names
- `catalog.composites` — list of `CompositeDefinition` names
- `catalog.presets` — list of `PresetDefinition` names

When `item_types` includes `ItemType.ALL`, expand to `[EFFECT, COMPOSITE, PRESET]`.

Each (item_type, name) pair becomes a single processing request. The enumeration collects all pairs before processing starts to provide accurate `total` count upfront.

### Parallel Execution

Use `concurrent.futures.ThreadPoolExecutor` with `max_workers` from `BatchRequest`:
```python
with ThreadPoolExecutor(max_workers=request.max_workers) as executor:
    futures = {executor.submit(self._process_one, item): item for item in items}
    for future in as_completed(futures):
        item = futures[future]
        try:
            result = future.result()
            results.append(result)
            if result.success:
                succeeded += 1
            else:
                failed += 1
                if request.strict:
                    break
        except Exception as e:
            failed += 1
            if request.strict:
                break
```

For sequential mode:
```python
for item in items:
    result = self._process_one(item)
    results.append(result)
    if not result.success and request.strict:
        break
```

### Input Path Handling

- If `input_path` is a file, process that single file against the catalog scope
- If `input_path` is a directory, walk for supported image files (`*.png`, `*.jpg`, `*.jpeg`)
- If `input_path` does not exist, raise `NoInputFilesError`
- If no matching files found (empty directory), return `BatchResult(total=0, ...)`

### Output Directory Resolution

Use the existing `OutputPathService.batch_output_dir`:
```python
output_dir = self._output_path_service.batch_output_dir(
    input_path=request.input_path,
    output_dir=request.output_dir,
    flat=request.flat,
    explicit_output=request.explicit_output,
)
```

### Error Handling

- Per-item `ProcessingResult` catches all exceptions at the item level
- `KeyboardInterrupt` during batch returns partial results (items completed so far)
- Strict mode: after failure, remaining in-flight parallel tasks may complete but no new items start
- Non-strict mode: all items process regardless of individual failures

### Existing CLI Patterns to Follow

Story 2.3 (`cli/process.py`) established the pattern:
- `_resolve_context` extracts `ctx.obj` settings into an `AppSettings` override dict
- `_resolve_processor` dispatches to the right processor based on runtime mode + dry-run
- The batch CLI command should follow the same pattern, reusing `_resolve_context` and `_resolve_processor`

From `cli/main.py:42-47`:
- `--runtime` flag validated against `RuntimeMode` enum
- `--container-engine` flag validated against `ContainerEngine` enum
- Both stored in `ctx.obj`

### Testing Strategy

- **Unit tests** for `BatchProcessor` with a mock `EffectProcessorPort` (use `unittest.mock.MagicMock` or a `MockProcessor` that returns controlled results)
- **CLI integration tests** via `CliRunner` (existing pattern in `tests/unit/cli/test_process_commands.py`)
- **No need to re-test output adapters** — they're already tested for `batch_result`

### Not in Scope for This Story

- Output path semantics `flat`/`explicit_output` — covered by Story 3.2
- Strict/parallel control modes beyond basic wiring — full behavior covered by Story 3.3
- These flags are accepted but minimally wired in this story

## Dev Agent Record

### File List

- NEW: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/batch_processor.py`
- NEW: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/batch.py`
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/main.py` — register batch subcommand
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/enums.py` — add `ALL` to `ItemType`
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/exceptions.py` — add batch errors if needed
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/factory.py` — add `create_batch_processor`
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/errors.py` — re-export if needed
- NEW: `src/cli-tools/wallpaper-effects-generator/tests/unit/adapters/test_batch_processor.py`
- UPDATE: `src/cli-tools/wallpaper-effects-generator/tests/unit/cli/test_process_commands.py` — or new `src/cli-tools/wallpaper-effects-generator/tests/unit/cli/test_batch_commands.py`

### Reference Source Paths

- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/models.py` — `BatchRequest`, `BatchResult`, `ProcessingResult`, `EffectsCatalog`
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/enums.py` — `ItemType`, `RuntimeMode`, `ContainerEngine`
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/exceptions.py` — existing error hierarchy
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/services.py` — `OutputPathService.batch_output_dir`
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/ports/processor.py` — `EffectProcessorPort` protocol including `process_batch`
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/local_processor.py` — existing single-item processor pattern
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/factory.py` — existing factory functions and `CliDependencies` dataclass
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/main.py` — CLI entry point, runtime/engine flags
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/process.py` — `_resolve_context`, `_resolve_processor` patterns
- `_bmad-output/implementation-artifacts/2-3-runtime-mode-selection-error-mapping.md` — CLI wiring patterns
- `_bmad-output/implementation-artifacts/1-1-domain-models-resolution-contracts.md` — domain model contracts
- `_bmad-output/implementation-artifacts/1-4-multi-format-output-adapters.md` — output adapter patterns
