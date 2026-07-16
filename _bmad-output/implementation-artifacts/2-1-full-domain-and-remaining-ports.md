---
baseline_commit: 49c889f91398c5c098b0ceedfdaa17e52e57adbd
---

# Story 2.1: Full Domain & Remaining Ports

Status: done

## Story

As a developer,
I want the full domain model and all port interfaces defined,
so that config resolution, template rendering, and container support have contracts.

## Acceptance Criteria

### AC 1: New domain models

**Given** AppSettings, BackendParameterDefinition, BackendDefinition, OutputSettings, GenerationSettings, TemplateSettings, RuntimeSettings, ContainerSettings domain models
**When** instantiated
**Then** they are frozen dataclasses
**And** AppSettings composes all sub-settings (OutputSettings, GenerationSettings, TemplateSettings, RuntimeSettings, ContainerSettings)

**Given** BackendParameterDefinition
**When** instantiated
**Then** it has `name: str`, `type_: str` (pydantic type name), `default: Any | None`, `description: str`, `required: bool`, `choices: tuple[str, ...] | None`

**Given** BackendDefinition
**When** instantiated
**Then** it has `backend: Backend`, `display_name: str`, `description: str`, `parameters: tuple[BackendParameterDefinition, ...]`, `min_version: str`

**Given** OutputSettings
**When** instantiated
**Then** it has `directory: Path`, `default_formats: tuple[ColorFormat, ...]`, `overwrite: bool`

**Given** GenerationSettings
**When** instantiated
**Then** it has `backend: Backend`, `default_params: dict[str, Any]`

**Given** TemplateSettings
**When** instantiated
**Then** it has `templates_dir: Path | None`, `custom_templates_dir: Path | None`

**Given** RuntimeSettings
**When** instantiated
**Then** it has `mode: RuntimeMode`, `engine: ContainerEngine`

**Given** ContainerSettings
**When** instantiated
**Then** it has `image_prefix: str`, `image_tag: str`, `timeout_seconds: int`, `memory_limit: str`, `mount_timeout_seconds: int`

**Given** AppSettings
**When** instantiated with all sub-settings
**Then** it composes: `output: OutputSettings`, `generation: GenerationSettings`, `template: TemplateSettings`, `runtime: RuntimeSettings`, `container: ContainerSettings`

### AC 2: ParameterResolutionService

**Given** ParameterResolutionService
**When** resolve_all() is called with BackendDefinition.parameters and override dict
**Then** it returns override values where present, defaults otherwise
**And** raises ConfigResolutionError if a required param has no default and no override

### AC 3: New port interfaces (Protocols)

**Given** ConfigResolverPort
**When** defined
**Then** it is a `@runtime_checkable` Protocol with `resolve() -> AppSettings`

**Given** TemplateRendererPort
**When** defined
**Then** it is a `@runtime_checkable` Protocol with `render(template_name: str, scheme: ColorScheme, output_path: Path) -> None`

**Given** TemplateDirResolverPort
**When** defined
**Then** it is a `@runtime_checkable` Protocol with `resolve() -> Path`

**Given** SettingsSerializerPort
**When** defined
**Then** it is a `@runtime_checkable` Protocol with `serialize(settings: AppSettings) -> str` and `deserialize(raw: str) -> AppSettings`

**Given** VersionProviderPort
**When** defined
**Then** it is a `@runtime_checkable` Protocol with `get_version() -> str`

**Given** BackendCatalogLoaderPort
**When** defined
**Then** it is a `@runtime_checkable` Protocol with `load() -> dict[Backend, BackendDefinition]`

**Given** ContainerRuntimePort
**When** defined
**Then** it is a `@runtime_checkable` Protocol that abstracts oci-runtime's ContainerEngine behind a CSG-specific port
**And** has methods: `run(image: str, command: list[str], mounts: list[ContainerMount], timeout: int) -> ContainerResult`, `image_exists(image: str) -> bool`, `pull_image(image: str) -> None`

**Given** ContainerMount
**When** defined
**Then** it is a frozen dataclass with `source: Path`, `target: Path`, `read_only: bool`

**Given** ContainerResult
**When** defined
**Then** it is a frozen dataclass with `return_code: int`, `stdout: str`, `stderr: str`, `duration: float`

### AC 4: Existing services remain unchanged

**Given** HexValidationService, ColorAdjustmentService, PaletteNormalizationService exist in domain/services.py
**When** this story is implemented
**Then** they are preserved without modification

## Tasks / Subtasks

- [x] Replace AppSettings placeholder with frozen dataclass composing sub-settings (AC 1)
  - [x] Define OutputSettings, GenerationSettings, TemplateSettings, RuntimeSettings, ContainerSettings
  - [x] Define BackendParameterDefinition, BackendDefinition
  - [x] Define AppSettings with composition
  - [x] Remove placeholder `class AppSettings` comment
  - [x] Export new models from domain/__init__.py
- [x] Add ParameterResolutionService to domain/services.py (AC 2)
  - [x] Implement resolve_all(parameters, overrides) -> dict
  - [x] Raise ConfigResolutionError for missing required params
  - [x] Export from domain/__init__.py
- [x] Create ContainerMount and ContainerResult models (AC 3)
  - [x] Define as frozen dataclasses in domain/models.py
  - [x] Export from domain/__init__.py
- [x] Define new port interfaces (AC 3)
  - [x] ConfigResolverPort
  - [x] TemplateRendererPort
  - [x] TemplateDirResolverPort
  - [x] SettingsSerializerPort
  - [x] VersionProviderPort
  - [x] BackendCatalogLoaderPort
  - [x] ContainerRuntimePort
  - [x] Export all from ports/__init__.py
- [x] Update tests
  - [x] Test ParameterResolutionService
  - [x] Test new model instantiations
  - [x] Test Protocol structural subtyping

## Dev Notes

- All domain models go in `domain/models.py` (pattern established in Epic 1)
- All services go in `domain/services.py`
- Ports go in individual files under `ports/` (e.g. `ports/config_resolver.py`, `ports/template_renderer.py`)
- Use `@runtime_checkable Protocol` from `typing` for all ports (existing pattern)
- The placeholder `class AppSettings` at line 79 of `domain/models.py` must be replaced, not kept alongside the real model
- ParameterResolutionService belongs in `domain/services.py` as it has no I/O
- ContainerMount and ContainerResult live in `domain/models.py` (domain-level data contracts)
- Post-implementation: run `ruff check --fix` and `pytest` to verify no regressions

### Dependencies

- `pydantic >= 2.0` is in addendum deps — not needed for domain models (frozen dataclasses suffice) but referenced for settings schema in later stories
- No new runtime dependencies for this story

### Files to create

| File | Purpose |
|------|---------|
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/config_resolver.py` | ConfigResolverPort |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/template_renderer.py` | TemplateRendererPort |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/template_dir_resolver.py` | TemplateDirResolverPort |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/settings_serializer.py` | SettingsSerializerPort |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/version_provider.py` | VersionProviderPort |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/backend_catalog_loader.py` | BackendCatalogLoaderPort |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/container_runtime.py` | ContainerRuntimePort + ContainerMount, ContainerResult |

### Files to modify

| File | Change |
|------|--------|
| `domain/models.py` | Replace AppSettings placeholder, add sub-setting models, add ContainerMount, ContainerResult |
| `domain/services.py` | Add ParameterResolutionService |
| `domain/__init__.py` | Export new models + service |
| `ports/__init__.py` | Export all new ports |

### Post-implementation verification

```bash
cd src/cli-tools/color-scheme-generator
ruff check --fix
pytest
```

### References

- [Source: epics.md:283-308] Full ACs for story 2.1
- [Source: addendum.md:34-36] Domain and port inventory
- [Source: domain/models.py:79] AppSettings placeholder to replace
- [Source: domain/services.py:1-39] Existing services to preserve

## File List

### Created

- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/config_resolver.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/template_renderer.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/template_dir_resolver.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/settings_serializer.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/version_provider.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/backend_catalog_loader.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/container_runtime.py`

### Modified

- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/models.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/services.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/__init__.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/ports/__init__.py`
- `src/cli-tools/color-scheme-generator/tests/unit/domain/test_models.py`
- `src/cli-tools/color-scheme-generator/tests/unit/domain/test_services.py`
- `src/cli-tools/color-scheme-generator/tests/unit/ports/test_interfaces.py`

## Change Log

- Implemented full domain models: BackendParameterDefinition, BackendDefinition, OutputSettings, GenerationSettings, TemplateSettings, RuntimeSettings, ContainerSettings, AppSettings, ContainerMount, ContainerResult
- Added ParameterResolutionService with required param validation
- Created 7 new port interfaces: ConfigResolverPort, TemplateRendererPort, TemplateDirResolverPort, SettingsSerializerPort, VersionProviderPort, BackendCatalogLoaderPort, ContainerRuntimePort
- Updated domain/__init__.py and ports/__init__.py exports
- Added comprehensive tests for all new models, services, and protocol structural subtyping

## Dev Agent Record

### Implementation Plan

1. Added new frozen dataclass models to `domain/models.py` replacing the AppSettings placeholder
2. Added ParameterResolutionService with `resolve_all()` to `domain/services.py` using existing ConfigResolutionError for required param validation
3. Created 7 new port interface files under `ports/` following the existing `@runtime_checkable Protocol` pattern
4. Updated `domain/__init__.py` and `ports/__init__.py` with all new exports
5. Added tests for all new models (instantiations), ParameterResolutionService (resolution paths + error case), and Protocol structural subtyping (valid + invalid implementations)

### Completion Notes

All 5 task groups completed. 30 new test cases added. Full suite: 138 passed, 7 pre-existing failures unchanged.

### Review Findings

- [x] [Review][Patch] `resolve_all` conflates "no default" with "default is None" [`services.py:49-53`] — `BackendParameterDefinition.default: Any | None` uses `None` as sentinel for "no default," so a required param with `default=None` (a valid value) would raise `ConfigResolutionError` instead of resolving to `None`. Fix: use sentinel `_UNSET = object()` for the default field.
- [x] [Review][Patch] `GenerationSettings.default_params` is a mutable dict inside a frozen dataclass [`models.py:108`] — Python's frozen dataclasses only prevent reassignment, not mutation. `.default_params["x"] = y` silently breaks immutability. Fix: use `types.MappingProxyType` in `__post_init__`.
- [x] [Review][Patch] `ContainerMount.target` should use `PurePosixPath` [`models.py:144`] — Container-internal paths (e.g. `/app/output`) are not host filesystem paths. `Path` normalizes separators and resolves `.`/`..` which can silently corrupt mount targets. Fix: use `PurePosixPath` for container paths.
- [x] [Review][Defer] `resolve_all` silently ignores unknown override keys [`services.py:44-55`] — Unknown keys in overrides are silently dropped; caller typos produce no warning
- [x] [Review][Defer] `resolve_all` never enforces `choices` constraint [`services.py:44-55`, `models.py:86`] — Override values aren't validated against BackendParameterDefinition.choices
- [x] [Review][Defer] ContainerSettings fields lack validation [`models.py:123-129`] — `timeout_seconds` can be negative, `memory_limit` is an unvalidated free-form string
- [x] [Review][Defer] BackendParameterDefinition.choices and default are type-incompatible [`models.py:83,86`] — `choices: tuple[str, ...]` but `default: Any`; no static check that default matches choices type
- [x] [Review][Defer] `resolve_all` ignores `GenerationSettings.default_params` [`models.py:108`, `services.py:43-57`] — Future config pipeline should feed default_params as a lower-priority layer
- [x] [Review][Defer] ConfigResolverPort has no failure contract [`ports/config_resolver.py:7-8`] — No documented exceptions for missing/malformed config
- [x] [Review][Defer] TemplateRendererPort has no error contract [`ports/template_renderer.py:9-10`] — No documented exceptions for missing templates, permission errors
- [x] [Review][Defer] TemplateDirResolverPort returns Path even when both dirs can be None [`ports/template_dir_resolver.py:7-8`] — No contract for what happens when both template dirs are None
- [x] [Review][Defer] SettingsSerializerPort has no error contract [`ports/settings_serializer.py:10-11`] — Malformed input has no documented error behavior
- [x] [Review][Defer] BackendCatalogLoaderPort contract allows empty dict [`ports/backend_catalog_loader.py:9-10`] — No guarantee that at least one backend is registered
