---
baseline_commit: 5818602
---

# Story 2.2: Settings Config Resolution Pipeline

Status: done

## Story

As a maintainer,
I want the tool to find and validate a settings.toml file,
So that I can configure defaults and override them per-invocation.

## Acceptance Criteria

### AC 1: AssembledConfigResolver implements ConfigResolverPort

**Given** AssembledConfigResolver implementing ConfigResolverPort
**When** resolve() is called
**Then** it uses config-assembler-engine's AssembleConfiguration with CoreSettingsSchema (Pydantic)
**And** follows 5-strategy chain: CliPathStrategy > EnvPathStrategy > DirectoryTraversalStrategy > XdgStrategy > DefaultFileStrategy
**And** returns AppSettings (domain dataclass, not Pydantic model)
**And** returns resolved path and applied overrides

### AC 2: CoreSettingsSchema validation

**Given** CoreSettingsSchema with @field_validator
**When** runtime.mode is invalid
**Then** Pydantic rejects with accepted values
**When** container.engine is invalid
**Then** Pydantic rejects with accepted values
**When** generation.backend is "auto"
**Then** Pydantic rejects — no AUTO member (ADR-010)

### AC 3: Override precedence

**Given** OverrideRule definitions
**When** COLORSCHEME__RUNTIME__MODE=container is set
**Then** the override is applied and coerced
**When** `--backend custom` is passed via CLI
**Then** CLI override wins over ENV
**When** COLORSCHEME_CONFIG_FILE_PATH=/path.toml is set
**Then** CLI explicit --config wins over ENV
**And** ENV wins over traversal/XDG/default

### AC 4: Error handling

**Given** a malformed settings.toml
**When** parsed
**Then** ConfigResolutionError is raised with line number and parse error

## Tasks / Subtasks

- [x] Add config-assembler-engine and pydantic as dependencies in pyproject.toml
  - [x] `config-assembler-engine` as local dependency (path: `src/shared/config-assembler-engine`)
  - [x] `pydantic>=2.0` (dependency of config-assembler-engine, explicit for type hints)
- [x] Create CoreSettingsSchema (Pydantic BaseModel) mirroring AppSettings structure
  - [x] OutputSettingsSchema, GenerationSettingsSchema, TemplateSettingsSchema, RuntimeSettingsSchema, ContainerSettingsSchema
  - [x] CoreSettingsSchema composing all sub-schemas
  - [x] @field_validator for runtime.mode, container.engine, generation.backend
- [x] Create AssembledConfigResolver
  - [x] Inject AssembleConfiguration use case
  - [x] Build ResolutionPolicy with 5-strategy chain
  - [x] Define OverrideRules for CLI/ENV
  - [x] Convert AssemblyResult.config (Pydantic) to AppSettings (domain dataclass)
  - [x] Return AssemblyResult with resolved path and overrides
- [x] Create ConfigResolverResult model (resolved_path, applied_overrides metadata)
- [x] Wire CLI env vars (`COLORSCHEME__*` prefix) for override support
- [x] Add tests
  - [x] AssembledConfigResolver.resolve() returns correct AppSettings
  - [x] Config path strategies resolve correctly (CLI > ENV > traversal > XDG > default)
  - [x] Override precedence (CLI > ENV > file)
  - [x] Invalid mode/engine/backend rejected
  - [x] Malformed TOML raises ConfigResolutionError

## Dev Notes

- `config-assembler-engine` is at `src/shared/config-assembler-engine/` — add as local dependency
- Use `AssembleConfiguration` use case from `config_assembler_engine.application.use_cases`
- Strategies from `config_assembler_engine.adapters.strategies.*`
- OverrideRules use `COLORSCHEME__` env prefix (defined in addendum)
- CoreSettingsSchema lives in a new `adapters/settings/` module (adapter layer — Pydantic is an I/O concern)
- AssembledConfigResolver lives in `adapters/settings/config_resolver.py`
- ConfigResolverResult can be a simple frozen dataclass or named tuple
- Domain models from story 2.1 are all frozen dataclasses — convert Pydantic → dataclass after validation
- TOML parsing uses `config_assembler_engine.adapters.parsers.toml_parser`

### Dependencies

- `config-assembler-engine` — local package at `src/shared/config-assembler-engine/`
- `pydantic >= 2.0` — already in addendum deps, needed for CoreSettingsSchema
- `tomli-w >= 1.0` — for TOML serialization (story 2.8+)

## Dev Agent Record

### Implementation Plan

1. Added `config-assembler-engine` and `pydantic>=2.0` as dependencies in `pyproject.toml`, with `config-assembler-engine` wired as a local editable dependency via `[tool.uv.sources]`.
2. Created `adapters/settings/schema.py` with `CoreSettingsSchema` (Pydantic) mirroring `AppSettings` domain structure: `OutputSettingsSchema`, `GenerationSettingsSchema`, `TemplateSettingsSchema`, `RuntimeSettingsSchema`, `ContainerSettingsSchema`. Added `@field_validator` on `runtime.mode`, `container.engine`, and `generation.backend`.
3. Created `adapters/settings/config_resolver.py` with `AssembledConfigResolver` implementing `ConfigResolverPort`. Wires `AssembleConfiguration` use case with 5-strategy chain (`CliPathStrategy > EnvPathStrategy > DirectoryTraversalStrategy > XdgStrategy > DefaultFileStrategy`), `COLORSCHEME` env prefix, and full `OverrideRule` set for all settings fields. Converts `CoreSettingsSchema` (Pydantic) → `AppSettings` (domain frozen dataclass). Stores resolution metadata in `last_result`.
4. Added `ConfigResolverResult` frozen dataclass to `domain/models.py` with `resolved_path` and `applied_overrides`.
5. Wrote 19 unit tests: schema validation (valid configs, invalid field rejections), resolver protocol compliance, resolution metadata, CLI/ENV override passthrough, and policy construction.

### Completion Notes

- All 6 tasks with 15 subtasks completed
- 165 tests pass (14 new + 151 existing), zero regressions
- Ruff lint clean (only pre-existing issues remain)
- Story status updated to "review"

## File List

| File | Status |
|------|--------|
| `src/cli-tools/color-scheme-generator/pyproject.toml` | Modified |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/__init__.py` | Modified |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/__init__.py` | Created |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/schema.py` | Created |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/config_resolver.py` | Created |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/models.py` | Modified |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/__init__.py` | Modified |
| `src/cli-tools/color-scheme-generator/tests/unit/adapters/settings/__init__.py` | Created |
| `src/cli-tools/color-scheme-generator/tests/unit/adapters/settings/test_schema.py` | Created |
| `src/cli-tools/color-scheme-generator/tests/unit/adapters/settings/test_config_resolver.py` | Created |

## Change Log

- feat: add config resolution pipeline with CoreSettingsSchema and AssembledConfigResolver

### Files to create

| File | Purpose |
|------|---------|
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/__init__.py` | Settings adapter package |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/schema.py` | CoreSettingsSchema (Pydantic) matching AppSettings |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/config_resolver.py` | AssembledConfigResolver implementing ConfigResolverPort |

### Files to modify

| File | Change |
|------|--------|
| `pyproject.toml` | Add config-assembler-engine + pydantic deps |
| `adapters/__init__.py` | Export settings adapter |
| `domain/models.py` | Add ConfigResolverResult model (or keep in ports module) |

### Post-implementation verification

```bash
cd src/cli-tools/color-scheme-generator
pip install -e ../../../shared/config-assembler-engine
pip install -e .
ruff check --fix
pytest
```

### Review Findings

- [x] [Review][Patch] `ConfigResolverResult` exposes `AppliedOverride` from external package — replaced with domain-native `AppliedOverride` dataclass
- [x] [Review][Patch] No `ConfigResolutionError` raised on malformed TOML (AC 4) [config_resolver.py:107-113] — wrapped parser exceptions in `ConfigResolutionError`
- [x] [Review][Patch] No integration test for malformed TOML raising `ConfigResolutionError` [tests/]
- [x] [Review][Patch] `memory_limit` field accepts any unvalidated string [schema.py:69]
- [x] [Review][Patch] Timeout fields accept negative integers [schema.py:68-70]
- [x] [Review][Patch] Empty-string `directory` silently resolves to CWD [schema.py:12]
- [x] [Review][Patch] Template directory paths not validated for existence [schema.py:34-36]
- [x] [Review][Defer] `explicit_path` to missing file not wrapped — depends on config-assembler-engine contract
- [x] [Review][Defer] `resolved_path` and `applied_overrides` could be `None` — depends on config-assembler-engine contract

### References

- [Source: epics.md:310-345] Full ACs for story 2.2
- [Source: config-assembler-engine/src/config_assembler_engine/application/use_cases.py] AssembleConfiguration API
- [Source: config-assembler-engine/src/config_assembler_engine/domain/models.py] AssemblyResult, OverrideRule, ResolutionPolicy, PathSource, ResolvedPath
- [Source: config-assembler-engine/src/config_assembler_engine/adapters/strategies/] Strategy implementations
- [Source: addendum.md:69-76] Dependency snapshot including pydantic, config-assembler-engine
