---
baseline_commit: 03dfed3d6915c7f8c26f0b6c96ceceb296ceb654
---

# Story 2.3: Backend YAML Catalog Resolution

Status: review

## Story

As a maintainer,
I want backend parameter definitions loaded from a backends.yaml catalog file,
So that I can inspect and edit per-backend parameters without touching code.

## Acceptance Criteria

### AC 1: YamlBackendCatalogLoader implements BackendCatalogLoaderPort

**Given** YamlBackendCatalogLoader implementing BackendCatalogLoaderPort
**When** load() is called
**Then** it resolves backends.yaml via config-assembler-engine's AssembleConfiguration with YamlConfigParser and BackendsCatalogSchema (Pydantic)
**And** follows the same 5-strategy chain as settings: CliPathStrategy > EnvPathStrategy > DirectoryTraversalStrategy > XdgStrategy > DefaultFileStrategy
**And** uses env prefix COLORSCHEME_BACKENDS
**And** returns dict[Backend, BackendDefinition]
**And** no OverrideRules apply — catalog content is file-source only

### AC 2: BackendsCatalogSchema validates YAML structure

**Given** BackendsCatalogSchema (Pydantic BaseModel)
**When** parsing valid backends.yaml with three backends
**Then** custom has parameters: saturation (float, 0-2, default 1.0), n_clusters (int, 1-32, default 16), algorithm (str, choices=["kmeans"])
**And** pywal has parameters: saturation + algorithm (choices=["auto","thief","color","haishoku","colorthief","wal"])
**And** wallust has parameters: saturation + algorithm (choices=["kmeans","kmeans-new","kmeans-old","kmeans-improved","fastkmeans","kmeans-euclid","pam","pam-new","pam-old"])
**When** a backend definition has an invalid param_type
**Then** Pydantic rejects with accepted values
**When** a required field is missing
**Then** Pydantic raises validation error

### AC 3: Schema-to-domain conversion

**Given** a validated BackendsCatalogSchema
**When** _schema_to_domain() converts to dict[Backend, BackendDefinition]
**Then** Backend enum members map correctly (custom -> CUSTOM, pywal -> PYWAL, wallust -> WALLUST)
**And** BackendParameterDefinition fields map: key -> name, param_type -> type_, choices -> tuple
**And** min/max constraints are carried through (domain BackendParameterDefinition currently lacks min/max — add them if the architecture plan requires validation on this side; otherwise store as metadata or validated at coercion time)
**And** BackendDefinition.display_name defaults to backend.value.title() or the description prefix

### AC 4: Default bundled backends.yaml

**Given** the package defaults/backends.yaml
**When** loaded via DefaultFileStrategy
**Then** it contains all three backends with their parameter definitions as specified in the architecture plan §14
**And** the YAML validates against BackendsCatalogSchema

### AC 5: Error handling

**Given** a corrupt or unparseable backends.yaml
**When** YamlConfigParser raises
**Then** ConfigResolutionError is raised with the file path and parse error
**Given** a backends.yaml missing required fields
**When** Pydantic validation fails
**Then** ConfigResolutionError wraps the Pydantic validation error

## Tasks / Subtasks

- [x] Create BackendsCatalogSchema (Pydantic) in adapters/schemas/ (AC: 2)
  - [x] BackendParameterSchema with: key, param_type, default, min, max, choices, description, required
  - [x] BackendDefinitionSchema with: description, parameters (list of BackendParameterSchema), display_name
  - [x] BackendsCatalogSchema: dict[str, BackendDefinitionSchema] (keyed by backend name)
  - [x] @field_validator for param_type choices (float, int, str)
- [x] Create YamlBackendCatalogLoader in adapters/yaml_backend_catalog_loader.py (AC: 1, 3)
  - [x] Inject AssembleConfiguration use case with YamlConfigParser
  - [x] Build ResolutionPolicy with 5-strategy chain (env prefix COLORSCHEME_BACKENDS)
  - [x] Build OverrideRules: empty (catalog is file-source only)
  - [x] Implement _schema_to_domain(): BackendsCatalogSchema -> dict[Backend, BackendDefinition]
  - [x] Create adapters/schemas/__init__.py
- [x] Create defaults/backends.yaml with all three backend definitions (AC: 4)
- [x] Update factory.py to wire YamlBackendCatalogLoader (AC: 1)
  - [x] Add create_backend_catalog_loader() helper
  - [x] Store on CliDependencies
- [x] Add tests (AC: 2, 3, 5)
  - [x] BackendsCatalogSchema validates valid YAML
  - [x] BackendsCatalogSchema rejects invalid param_type
  - [x] BackendsCatalogSchema rejects missing required fields
  - [x] YamlBackendCatalogLoader.load() returns correct dict[Backend, BackendDefinition]
  - [x] YamlBackendCatalogLoader.load() raises ConfigResolutionError on corrupt YAML
  - [x] YamlBackendCatalogLoader protocol compliance (isinstance check)
  - [x] Integration: load default bundled backends.yaml and verify structure

## Dev Notes

- config-assembler-engine provides:
  - `AssembleConfiguration` use case at `config_assembler_engine.application.use_cases`
  - `YamlConfigParser` at `config_assembler_engine.adapters.parsers.yaml_parser`
  - Strategy classes at `config_assembler_engine.adapters.strategies.*`
  - `PydanticTypeCoercer` at `config_assembler_engine.adapters.type_coercer`
- Same wiring pattern as AssembledConfigResolver in `adapters/settings/config_resolver.py`
- Key differences from settings resolver: use YamlConfigParser (not TomlConfigParser), empty OverrideRules, BackendsCatalogSchema (not CoreSettingsSchema)
- BackendCatalogLoaderPort already exists at `ports/backend_catalog_loader.py`
- Domain models BackendParameterDefinition and BackendDefinition exist at `domain/models.py:82-98`
- Current BackendParameterDefinition lacks min/max fields — if the architecture requires validation-side min/max enforcement (not just metadata), add them; otherwise they're validated at the Pydantic schema level only
- Pydantic lives only at adapter boundary (ADR-012) — BackendsCatalogSchema is in adapters/schemas/
- YamlBackendCatalogLoader lives in `adapters/yaml_backend_catalog_loader.py`
- Consider naming: the architecture plan uses `adapters/schemas/backends_catalog_schema.py` for the schema
- Resolution prefix: COLORSCHEME_BACKENDS (e.g. `COLORSCHEME_BACKENDS_CONFIG_FILE_PATH`)
- Default file: package-bundled `defaults/backends.yaml`

### Project Structure Notes

- Mirror of the settings resolver pattern: assembled_config_resolver.py + schema in adapters/settings/
- This story creates a parallel `adapters/schemas/` package (distinct from `adapters/settings/`)
- Adapts existing `adapters/__init__.py` to export the new schemas package

### References

- [Source: epics.md:346-366] Story 2.3 ACs
- [Source: ARCHITECTURE_PLAN.md:206-273] Backend YAML catalog resolution pipeline design (D11, §7)
- [Source: ARCHITECTURE_PLAN.md:39-40] BackendParameterDefinition domain model specs
- [Source: ARCHITECTURE_PLAN.md:578] ADR-011 — YAML catalog rationale
- [Source: ARCHITECTURE_PLAN.md:615-666] Default backends.yaml content
- [Source: story 2.2 at implementation-artifacts/2-2-settings-config-resolution-pipeline.md] AssembledConfigResolver pattern reference
- [Source: ports/backend_catalog_loader.py] Existing port interface
- [Source: domain/models.py:82-98] Existing BackendParameterDefinition, BackendDefinition
- [Source: domain/services.py:48-67] ParameterResolutionService — consumes BackendParameterDefinition
- [Source: config-assembler-engine/src/config_assembler_engine/adapters/parsers/yaml_parser.py] YamlConfigParser

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Dev Notes from Previous Story (2.2)

- config-assembler-engine is at `src/shared/config-assembler-engine/` — add as local dependency (already done in story 2.2)
- Strategies from `config_assembler_engine.adapters.strategies.*`
- OverrideRules use `COLORSCHEME__` env prefix; backends use `COLORSCHEME_BACKENDS` prefix
- Pydantic schemas live in adapter layer — domain never imports pydantic
- Domain models are frozen dataclasses — convert Pydantic → domain after validation
- Review finding: empty-string paths and missing-existence checks are concerns to validate
- 19 unit tests written for 2.2 settings resolver; similar pattern expected here

### File List

| File | Status |
|------|--------|
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/schemas/__init__.py` | Created |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/schemas/backends_catalog_schema.py` | Created |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/yaml_backend_catalog_loader.py` | Created |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/__init__.py` | Modified |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/backends.yaml` | Created |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/factory.py` | Modified |
| `src/cli-tools/color-scheme-generator/tests/unit/adapters/schemas/__init__.py` | Created |
| `src/cli-tools/color-scheme-generator/tests/unit/adapters/schemas/test_backends_catalog_schema.py` | Created |
| `src/cli-tools/color-scheme-generator/tests/unit/adapters/test_yaml_backend_catalog_loader.py` | Created |
| `_bmad-output/implementation-artifacts/2-3-backend-yaml-catalog-resolution.md` | Modified |

### Post-implementation verification

```bash
cd src/cli-tools/color-scheme-generator
pytest
ruff check --fix
```

### Implementation Plan

Followed the AssembledConfigResolver pattern from story 2.2. Key differences:
- Uses YamlConfigParser instead of TomlConfigParser
- Empty OverrideRules (catalog is file-source only)
- BackendsCatalogSchema uses RootModel for direct dict validation
- ResolutionPolicy with COLORSCHEME_BACKENDS env prefix
- _schema_to_domain() converts validated schema to domain models

### Dependencies Added

- None (used existing config-assembler-engine and pydantic)

### Test Coverage

- 8 unit tests for BackendsCatalogSchema (valid YAML, field structure, valid/invalid param_type, defaults, choices, missing required)
- 7 tests for YamlBackendCatalogLoader (protocol compliance, correct dict/domain values, schema/policy passing, error handling, integration with real file)

### Debug Log

- Schema initially used BaseModel with `backends:` wrapper field → changed to RootModel for direct dict validation matching the YAML structure
- Fixed import typo `config_adapters` → `config_assembler_engine` in loader
- Added missing `pass` to RootModel class body

### Completion Notes

- All tasks completed and verified
- All 181 existing tests + 15 new tests pass (no regressions)
- All linting checks pass
- Story status: review
