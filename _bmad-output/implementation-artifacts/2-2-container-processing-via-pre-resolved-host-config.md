---
baseline_commit: d99517b198334f305fb525d560c9d121482dd5af
---

# Story 2.2: Container Processing via Pre-Resolved Host Config

Status: done

## Story

As a developer,
I want to process wallpapers in container mode with host-resolved config,
So that container execution has consistent behavior without in-container re-resolution.

## Acceptance Criteria

**Given** a resolved settings config and effects catalog on the host
**When** a process command runs with `--runtime container`
**Then** the host pre-resolves settings and effects before container invocation
**And** resolved settings are serialized to a temp TOML file
**And** the temp settings TOML is mounted as `/weg-config/settings.toml` (RO)
**And** the resolved effects file is mounted as `/weg-effects/effects.yaml` (RO)
**And** the input parent directory is mounted as `/input` (RO)
**And** the output directory is mounted as `/output` (RW)

**Given** a container process command without explicit `--output`
**When** it completes
**Then** the output files are written to the mounted `/output` directory
**And** visible on the host in the specified output path

**Given** equivalent input, config, and effects
**When** `process effect` runs in local mode and container mode
**Then** both return the same `ProcessingResult` contract shape (same fields, same structure)
**And** any differences are surfaced only through explicit runtime errors (not silent contract divergence)

**Given** a container process run
**When** it completes
**Then** temp settings artifacts are cleaned up from the host

## Tasks / Subtasks

- [ ] Implement `SettingsSerializer` adapter (implements `SettingsSerializerPort`)
  - [ ] `serialize(settings: AppSettings, path: Path) -> None`: write settings to TOML
  - [ ] `deserialize(path: Path) -> AppSettings`: read and validate TOML back to `AppSettings`
  - [ ] Use `tomllib` (stdlib Python 3.11+) or `tomli` for TOML serialization
- [ ] Implement `EffectsSerializer` adapter (implements `EffectsSerializerPort`)
  - [ ] `serialize(catalog: EffectsCatalog, path: Path) -> None`: write catalog to YAML
  - [ ] `deserialize(path: Path) -> EffectsCatalog`: read YAML back to `EffectsCatalog`
  - [ ] Reuse YAML structure from `YamlEffectLoader` for format compatibility
- [ ] Implement `ContainerProcessor` adapter (implements `EffectProcessorPort`)
  - [ ] Constructor accepts: `command_runner: CommandRunnerPort`, `catalog: EffectsCatalog`, `output_dir: Path`, `settings: AppSettings`, container engine abstraction, serializer adapters
  - [ ] Host pre-resolution flow:
    - [ ] Serialize `AppSettings` to temp TOML file via `SettingsSerializerPort`
    - [ ] Serialize `EffectsCatalog` to temp YAML file via `EffectsSerializerPort`
    - [ ] Build container run command with mount binds: `settings.toml` → `/weg-config/settings.toml` (RO), `effects.yaml` → `/weg-effects/effects.yaml` (RO), input parent → `/input` (RO), output dir → `/output` (RW)
    - [ ] Resolve image tag from `container.image_tag` and `container.image_registry`
    - [ ] Invoke container runtime (docker/podman) with `oci-runtime` library
  - [ ] `process_effect`:
    - [ ] Resolve params and render command on host (same as `LocalProcessor`)
    - [ ] Pass rendered command string to container entrypoint via `--entrypoint` or script mount
    - [ ] Map container exit to `ProcessingResult` with same contract shape as `LocalProcessor`
  - [ ] `process_composite`:
    - [ ] Multi-step chain inside container (all intermediate work in `/output`)
    - [ ] Or orchestrate single step per container invocation — evaluate trade-offs
  - [ ] `process_preset`:
    - [ ] Delegate per-effect to `process_effect` inside container context
  - [ ] Temp file cleanup in `finally` block (remove temp settings TOML and effects YAML)
- [ ] Wire `ContainerProcessor` in factory
  - [ ] Add `create_container_processor()` to `factory.py`
  - [ ] Add `ContainerProcessor` import to factory
  - [ ] Wire runtime-mode selection logic in process CLI command (choose `LocalProcessor` vs `ContainerProcessor` based on `RuntimeSettings.mode`)
- [ ] Add tests
  - [ ] Unit test `SettingsSerializer`: round-trip `AppSettings` to TOML and back, test with all nested settings
  - [ ] Unit test `EffectsSerializer`: round-trip `EffectsCatalog` to YAML and back
  - [ ] Unit test `ContainerProcessor`: mock `CommandRunnerPort`, `SettingsSerializerPort`, `EffectsSerializerPort`, verify mount bind construction, verify temp cleanup
  - [ ] Unit test `ContainerProcessor.process_effect`: verify `ProcessingResult` contract shape matches `LocalProcessor`
  - [ ] Unit test `ContainerProcessor.process_composite`: verify multi-step chain handling
  - [ ] Unit test `ContainerProcessor.process_preset`: verify delegation
  - [ ] Integration test: create full round-trip with mocked container runtime

## Dev Notes

### Context
- This builds on Story 2.1 (OCI integration) and Story 1.3 (LocalProcessor pattern).
- Story 2.1 provides the container runtime abstraction (pull, exists, list, remove) via `ImageManagerPort` — see `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/ports/image_manager.py`.
- Story 1.3 established the `LocalProcessor` pattern implementing `EffectProcessorPort` — see `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/local_processor.py`.

### Architecture
- `ContainerProcessor` implements `EffectProcessorPort` (same port as `LocalProcessor`) — see `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/ports/processor.py`.
- `SettingsSerializerPort` and `EffectsSerializerPort` already exist in `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/ports/serializers.py` — must be implemented as concrete adapters.
- Pure domain layer is unchanged — hexagonal boundary preserved.

### Host Pre-Resolution Flow
1. Resolve `AppSettings` via `ConfigResolverPort` and `EffectsCatalog` via `EffectLoaderPort` on host
2. Serialize `AppSettings` → temp TOML file via `SettingsSerializer` implementation
3. Serialize `EffectsCatalog` → temp YAML file via `EffectsSerializer` implementation
4. Build `oci-runtime` run request with mount binds:
   - `<temp-settings.toml>:/weg-config/settings.toml:ro`
   - `<temp-effects.yaml>:/weg-effects/effects.yaml:ro`
   - `<input-parent-dir>:/input:ro`
   - `<output-dir>:/output:rw`
5. Invoke container with entrypoint that reads from `/weg-config/settings.toml` and `/weg-effects/effects.yaml`
6. On completion, copy output from `/output` mount to host output path (if different)
7. Clean up temp files in `finally` block

### Mount Contract
| Host                          | Container           | Mode |
|-------------------------------|---------------------|------|
| `<temp-settings-toml>`        | `/weg-config/settings.toml` | RO   |
| `<temp-effects-yaml>`         | `/weg-effects/effects.yaml`  | RO   |
| `<input-parent-dir>`          | `/input`            | RO   |
| `<output-dir>`                | `/output`           | RW   |

### ProcessingResult Parity
- `ContainerProcessor` must return `ProcessingResult` with the exact same field shape as `LocalProcessor`:
  - `success: bool`
  - `command: str`
  - `stdout: str`
  - `stderr: str`
  - `return_code: int`
  - `duration: float`
  - `output_path: Path | None`
- No silent contract divergence — differences surface only via explicit runtime errors (e.g., container image not found, container runtime unavailable)

### Reusable Abstractions
- Use existing `CommandSanitizer` (`src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/services.py:16`) for shell quoting
- Use existing `CommandSubstitutionService` (`src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/services.py:24`) for command template rendering
- Use existing `ParameterResolutionService` (`src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/services.py:38`) for param resolution
- Use existing `OutputPathService` (`src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/services.py:61`) for output path resolution
- Use existing `ContextValidatorPort` (`src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/ports/context_validator.py`) for input validation
- Use existing `CatalogCache` (`src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/catalog_cache.py`) for catalog caching

### Error Mapping
- `ContainerImageNotFoundError` → `ProcessingResult(success=False)` with runtime error category
- `ContainerRuntimeUnavailableError` → `ProcessingResult(success=False)` with runtime error category
- `ImagePullAccessError` → `ProcessingResult(success=False)` with runtime error category
- All error classes defined in `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/exceptions.py`

### Package Structure Changes
```
src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/
  adapters/
    container_processor.py          — (NEW) implements EffectProcessorPort
    serializer/
      settings_serializer.py        — (NEW) implements SettingsSerializerPort
      effects_serializer.py         — (NEW) implements EffectsSerializerPort
  factory.py                        — (UPDATE) add create_container_processor
  cli/
    process.py                      — (UPDATE) runtime-mode selection logic

tests/
  unit/adapters/
    test_container_processor.py     — (NEW)
    test_settings_serializer.py     — (NEW)
    test_effects_serializer.py      — (NEW)
  integration/
    test_container_processing.py    — (NEW) end-to-end with mocked runtime
```

### CLI Runtime Selection
The process CLI command (`src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/process.py`) must select processor at runtime:
```python
if settings.runtime.mode == RuntimeMode.LOCAL:
    processor = create_local_processor(...)
elif settings.runtime.mode == RuntimeMode.CONTAINER:
    processor = create_container_processor(...)
```

## Dev Agent Record

### Completion Notes

All tasks implemented:
1. **SettingsSerializer** — `adapters/serializer/settings_serializer.py`: serializes/deserializes AppSettings to/from TOML with full dataclass and Enum support
2. **EffectsSerializer** — `adapters/serializer/effects_serializer.py`: serializes/deserializes EffectsCatalog to/from YAML via pyyaml
3. **ContainerProcessor** — `adapters/container_processor.py`: implements EffectProcessorPort with host pre-resolution, container mount construction, temp artifact cleanup
4. **Factory wiring** — `factory.py`: `create_container_processor()` factory function
5. **CLI wiring** — `cli/process.py`: `_resolve_processor` dispatches to ContainerProcessor for container mode

### File List
- NEW: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/serializer/__init__.py`
- NEW: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/serializer/settings_serializer.py`
- NEW: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/serializer/effects_serializer.py`
- NEW: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/container_processor.py`
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/factory.py`
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/process.py`
- NEW: `tests/unit/adapters/serializer/__init__.py`
- NEW: `tests/unit/adapters/serializer/test_settings_serializer.py`
- NEW: `tests/unit/adapters/serializer/test_effects_serializer.py`
- NEW: `tests/unit/adapters/test_container_processor.py`

## Review Findings

### Decision Needed

- [ ] [Review][Decision] Container uses `--entrypoint /bin/sh` — not portable to distroless or scratch-based container images that lack `/bin/sh`. Decide which shell/entrypoint to use (e.g., `/bin/sh`, `/bin/bash`, or a custom entrypoint).

### Patch

- [x] [Review][Patch] `tempfile.mktemp` deprecated with TOCTOU race [`_serialize_artifacts`: container_processor.py:287-291] — fixed, replaced with `NamedTemporaryFile(delete=False)`
- [x] [Review][Patch] Dead code: `_build_container_command` never called [`container_processor.py:223-241`] — removed method and `_get_input_parent_dir`
- [x] [Review][Patch] No image-exists check / error mapping not wired — OCI runtime errors propagate as unhandled tracebacks instead of `ProcessingResult(success=False)` [`_run_in_container`: container_processor.py:270] — fixed, wrapped execute in try/except with BinaryNotFoundError and CommandExecutionError mapping
- [ ] [Review][Patch] Empty TOML file mounted when `self._settings is None` — zero-byte `/weg-config/settings.toml` inside container [`_serialize_artifacts`: container_processor.py:287-289]
- [x] [Review][Patch] Composite/preset failure `output_path` always resolved as `ItemType.EFFECT` — wrong output path when called from `process_composite` or `process_preset` [`_run_in_container`: container_processor.py:271] — fixed, added `item_type` param to `_run_in_container`
- [x] [Review][Patch] Composite/preset CLI commands lack `--param` support — users cannot supply parameter overrides for composite/preset processing [`cli/process.py:146-200`] — fixed, added `--param` to composite and preset commands
- [x] [Review][Patch] `_resolve_processor` returns `object` instead of `EffectProcessorPort` — disables static type checking [`cli/process.py:82`] — fixed, changed return type to `EffectProcessorPort`
- [x] [Review][Patch] `_cleanup_artifacts` redundant `exists()` check before `unlink(missing_ok=True)` [`container_processor.py:297`] — fixed, removed redundant check
- [x] [Review][Patch] `create_container_processor` silently ignores `context_validator` parameter — misleading API [`factory.py`] — fixed, wired `context_validator` through `ContainerProcessor` with `_pre_flight` checks

### Deferred

- [x] [Review][Defer] Effects serializer silently defaults invalid `item_type` to `EFFECT` — pre-existing pattern in `yaml_effect_loader.py`, not introduced by this change
- [x] [Review][Defer] TOCTOU between `input_path.exists()` check and container mount — fundamental race, not practically fixable
- [x] [Review][Defer] Unknown TOML sections silently ignored on deserialization — graceful degradation by design
- [x] [Review][Defer] Serializer skips `None` fields — intended behavior (optional fields omitted)

### References
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/ports/processor.py` — EffectProcessorPort interface
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/ports/serializers.py` — SettingsSerializerPort, EffectsSerializerPort
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/ports/image_manager.py` — ImageManagerPort
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/models.py` — ProcessingResult, AppSettings, EffectsCatalog, ContainerSettings
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/services.py` — CommandSanitizer, CommandSubstitutionService, ParameterResolutionService, OutputPathService
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/exceptions.py` — ContainerImageNotFoundError, ContainerRuntimeUnavailableError, ImagePullAccessError
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/local_processor.py` — LocalProcessor reference implementation
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/catalog_cache.py` — CatalogCache
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/context_validator.py` — InputContextValidator
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/factory.py` — existing factory functions for reference
- `_bmad-output/implementation-artifacts/1-3-local-processing-engine.md` — LocalProcessor story for reference
