# Story 2.2: Settings Config Resolution Pipeline

Status: ready-for-dev

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

- [ ] Add config-assembler-engine and pydantic as dependencies in pyproject.toml
  - [ ] `config-assembler-engine` as local dependency (path: `src/shared/config-assembler-engine`)
  - [ ] `pydantic>=2.0` (dependency of config-assembler-engine, explicit for type hints)
- [ ] Create CoreSettingsSchema (Pydantic BaseModel) mirroring AppSettings structure
  - [ ] OutputSettingsSchema, GenerationSettingsSchema, TemplateSettingsSchema, RuntimeSettingsSchema, ContainerSettingsSchema
  - [ ] CoreSettingsSchema composing all sub-schemas
  - [ ] @field_validator for runtime.mode, container.engine, generation.backend
- [ ] Create AssembledConfigResolver
  - [ ] Inject AssembleConfiguration use case
  - [ ] Build ResolutionPolicy with 5-strategy chain
  - [ ] Define OverrideRules for CLI/ENV
  - [ ] Convert AssemblyResult.config (Pydantic) to AppSettings (domain dataclass)
  - [ ] Return AssemblyResult with resolved path and overrides
- [ ] Create ConfigResolverResult model (resolved_path, applied_overrides metadata)
- [ ] Wire CLI env vars (`COLORSCHEME__*` prefix) for override support
- [ ] Add tests
  - [ ] AssembledConfigResolver.resolve() returns correct AppSettings
  - [ ] Config path strategies resolve correctly (CLI > ENV > traversal > XDG > default)
  - [ ] Override precedence (CLI > ENV > file)
  - [ ] Invalid mode/engine/backend rejected
  - [ ] Malformed TOML raises ConfigResolutionError

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

### References

- [Source: epics.md:310-345] Full ACs for story 2.2
- [Source: config-assembler-engine/src/config_assembler_engine/application/use_cases.py] AssembleConfiguration API
- [Source: config-assembler-engine/src/config_assembler_engine/domain/models.py] AssemblyResult, OverrideRule, ResolutionPolicy, PathSource, ResolvedPath
- [Source: config-assembler-engine/src/config_assembler_engine/adapters/strategies/] Strategy implementations
- [Source: addendum.md:69-76] Dependency snapshot including pydantic, config-assembler-engine
