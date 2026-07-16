# Story 2.1: Full Domain & Remaining Ports

Status: ready-for-dev

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

- [ ] Replace AppSettings placeholder with frozen dataclass composing sub-settings (AC 1)
  - [ ] Define OutputSettings, GenerationSettings, TemplateSettings, RuntimeSettings, ContainerSettings
  - [ ] Define BackendParameterDefinition, BackendDefinition
  - [ ] Define AppSettings with composition
  - [ ] Remove placeholder `class AppSettings` comment
  - [ ] Export new models from domain/__init__.py
- [ ] Add ParameterResolutionService to domain/services.py (AC 2)
  - [ ] Implement resolve_all(parameters, overrides) -> dict
  - [ ] Raise ConfigResolutionError for missing required params
  - [ ] Export from domain/__init__.py
- [ ] Create ContainerMount and ContainerResult models (AC 3)
  - [ ] Define as frozen dataclasses in domain/models.py
  - [ ] Export from domain/__init__.py
- [ ] Define new port interfaces (AC 3)
  - [ ] ConfigResolverPort
  - [ ] TemplateRendererPort
  - [ ] TemplateDirResolverPort
  - [ ] SettingsSerializerPort
  - [ ] VersionProviderPort
  - [ ] BackendCatalogLoaderPort
  - [ ] ContainerRuntimePort
  - [ ] Export all from ports/__init__.py
- [ ] Update tests
  - [ ] Test ParameterResolutionService
  - [ ] Test new model instantiations
  - [ ] Test Protocol structural subtyping

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
