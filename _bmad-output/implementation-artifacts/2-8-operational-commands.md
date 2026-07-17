# Story 2.8: Operational Commands (Info, Dump-Config, Dump-Templates, List-Backends)

Status: ready-for-dev

## Story

As a maintainer debugging a CI failure,
I want to inspect the resolved config, backends, and templates,
So that I can trace why extraction produced unexpected results.

## Acceptance Criteria

### AC 1: Info command

**Given** the info command
**When** `csg info` is run
**Then** it displays resolved settings.toml path and its source (CLI/ENV/XDG/DEFAULT)
**And** all applied overrides with source and coerced value
**And** effective runtime mode and container engine
**And** resolved templates directory
**And** backend availability for all three backends

### AC 2: Dump-Config command

**Given** the dump-config command
**When** `csg dump-config` is run
**Then** it outputs full resolved AppSettings as TOML to stdout
**When** `--output /path/file.toml --overwrite` is passed
**Then** it writes to file (overwriting if exists)

### AC 3: Dump-Templates command

**Given** the dump-templates command
**When** `csg dump-templates` is run
**Then** it copies all 8 bundled .j2 templates to XDG templates dir (mkdir parents)
**And** --overwrite replaces existing files; without it, skips existing files
**And** if a target file is read-only, raises OutputWriteError
**When** `--output /custom/path` is passed
**Then** it copies to the custom path

### AC 4: List-Backends command

**Given** the list-backends command
**When** `csg list-backends` is run
**Then** it shows each backend's name, description, host availability, image presence (container mode), and supported parameters with type/default/range

### AC 5: All four commands

**Given** all four commands
**When** run
**Then** they support --output-format json|rich|plain

## Tasks / Subtasks

### Adapter: TOML Settings Serializer (new)
- [ ] Create `adapters/settings/settings_serializer.py`
  - Implements `SettingsSerializerPort` (defined in `ports/settings_serializer.py`)
  - `serialize(settings: AppSettings) -> str`: converts AppSettings to TOML string
  - `deserialize(raw: str) -> AppSettings`: not needed for operational commands, but implement for contract compliance (raise `NotImplementedError` or minimal implementation)
  - TOML output must include all AppSettings fields: output, generation, template, runtime, container
  - Use f-string formatting to build TOML — no external `toml` library dependency (project doesn't have one). Keep it simple sections + key = value formatting
  - Handle Path → str conversion, Enum → value conversion, None → omit/empty
  - Boolean values output as `true`/`false`

### CLI: Info Command (new `cli/info_cmd.py`)
- [ ] Create `cli/info_cmd.py` with `info()` Typer command (AC: 1)
  - Accepts `ctx: typer.Context`
  - Resolves config via `deps.config_resolver.resolve()` — catches `ConfigResolutionError`
  - Gets resolver result from `config_resolver.last_result` (contains `resolved_path`, `applied_overrides`)
  - Gets `deps.backend_catalog_loader` for backend definitions (optional — resolve in info cmd if available)
  - Gets templates dir via `deps.template_dir_resolver.resolve()` — catches `ConfigResolutionError`
  - Checks backend availability: for each Backend enum member, call `deps.backend_registry[backend].is_available()`
  - Builds a structured dict with:
    - `config_path` and `config_source` from `last_result.resolved_path`
    - `applied_overrides` list
    - `runtime_mode`, `container_engine` from resolved AppSettings
    - `templates_directory` from resolver
    - `backends` dict with availability for each backend
  - Uses `deps.output_adapter` — needs a way to output structured data:
    - **For JSON**: output the structured dict directly via `print(json.dumps(...))`
    - **For Rich**: format as rich.table.Table with sections
    - **For Plain**: format as simple key=value lines
  - Note: `OutputPort` has no generic `message()` method. Handle info output by checking adapter type (pattern from `version_cmd.py`) OR use `process_result()` by wrapping info data into a minimal `GenerationResult`-like payload. **Recommended**: follow version_cmd pattern — check adapter type and format accordingly. Keep output formatting in the command handler.

### CLI: Dump-Config Command (new `cli/dump_config_cmd.py`)
- [ ] Create `cli/dump_config_cmd.py` with `dump_config()` Typer command (AC: 2)
  - Accepts `ctx: typer.Context`
  - Optional `--output` / `-o` Path argument, optional `--overwrite` / `-w` flag
  - Resolves config via `deps.config_resolver.resolve()` — catches `ConfigResolutionError`
  - Serializes to TOML via `SettingsSerializerPort.serialize()`
  - If no `--output`: prints to stdout
  - If `--output` given:
    - Check if file exists and `--overwrite` is not set → raise `OutputWriteError` or skip
    - Write file, catch permission errors → raise `OutputWriteError`
  - Uses `deps.output_adapter` to report success/failure (reuse `process_result` with a stub `GenerationResult`, or format inline)

### CLI: Dump-Templates Command (new `cli/dump_templates_cmd.py`)
- [ ] Create `cli/dump_templates_cmd.py` with `dump_templates()` Typer command (AC: 3)
  - Accepts `ctx: typer.Context`
  - Optional `--output` / `-o` custom target directory path
  - Optional `--overwrite` / `-w` flag (default: False)
  - Resolve target directory:
    - If `--output` given: use that
    - Otherwise: resolve via `deps.template_dir_resolver.resolve()` OR use XDG default: `~/.config/color-scheme-generator/templates/`
  - Find bundled templates via `importlib.resources`:
    ```python
    from importlib.resources import files as resource_files
    templates = resource_files("color_scheme_generator.defaults").joinpath("templates")
    ```
  - Iterate over bundled .j2 files:
    - For each file, construct target path under target dir
    - If target exists and not `--overwrite`: skip (log.info)
    - If target exists and `--overwrite`:
      - Check if writable. If not, raise `OutputWriteError(target_path, reason)`
      - Copy file content
    - If target doesn't exist: create parent dirs, copy file
  - Report summary via `deps.output_adapter` (how many copied, how many skipped)

### CLI: List-Backends Command (new `cli/list_backends_cmd.py`)
- [ ] Create `cli/list_backends_cmd.py` with `list_backends()` Typer command (AC: 4)
  - Accepts `ctx: typer.Context`
  - Load backend catalog via `deps.backend_catalog_loader.load()` — catches errors gracefully
  - For each Backend in `deps.backend_registry`:
    - Check `is_available()` on the host
    - Get `BackendDefinition` from catalog if available (with params, description)
    - Image presence (container mode): deferred (story 3.x) — set to `null`/`"not implemented"`
  - Build structured output with per-backend info
  - Format via `deps.output_adapter` (same pattern as info — check adapter type)

### Factory wiring (existing `factory.py`)
- [ ] Add `config_resolver: AssembledConfigResolver | None = None` to `CliDependencies` dataclass
- [ ] Add `create_config_resolver()` factory function
- [ ] Wire `config_resolver`, `backend_catalog_loader`, `template_dir_resolver` into `build_deps()` in `cli/main.py`
- [ ] Ensure `build_deps()` also calls `create_template_dir_resolver()`, `create_backend_catalog_loader()`, `create_config_resolver()`

### CLI: main.py (existing)
- [ ] Import and register the 4 new command functions:
  ```python
  from color_scheme_generator.cli.info_cmd import info
  from color_scheme_generator.cli.dump_config_cmd import dump_config
  from color_scheme_generator.cli.dump_templates_cmd import dump_templates
  from color_scheme_generator.cli.list_backends_cmd import list_backends

  app.command()(info)
  app.command()(dump_config)
  app.command()(dump_templates)
  app.command()(list_backends)
  ```
- [ ] Update `build_deps()` to wire all deps
- [ ] Keep `--output-format` global option from the callback (already done in story 2.7)

### Write tests

#### test_info_command.py (new)
- [ ] Test `csg info` outputs resolved config path (AC: 1)
- [ ] Test `csg info` shows applied overrides (AC: 1)
- [ ] Test `csg info` shows runtime mode + container engine (AC: 1)
- [ ] Test `csg info` shows templates directory (AC: 1)
- [ ] Test `csg info` shows backend availability (AC: 1)
- [ ] Test `csg info` supports --output-format (AC: 5)
- [ ] Test `csg info` handles ConfigResolutionError gracefully

#### test_dump_config_command.py (new)
- [ ] Test `csg dump-config` outputs TOML to stdout (AC: 2)
- [ ] Test `csg dump-config --output file.toml` writes file (AC: 2)
- [ ] Test `csg dump-config --output file.toml --overwrite` overwrites (AC: 2)
- [ ] Test `csg dump-config` handles config resolution failure (AC: 2)
- [ ] Test `csg dump-config` output is valid TOML (AC: 2)

#### test_dump_templates_command.py (new)
- [ ] Test `csg dump-templates` copies bundled templates (AC: 3)
- [ ] Test `csg dump-templates` creates parent directories (AC: 3)
- [ ] Test `csg dump-templates --overwrite` replaces existing (AC: 3)
- [ ] Test `csg dump-templates` without --overwrite skips existing (AC: 3)
- [ ] Test `csg dump-templates --output /custom/path` uses custom path (AC: 3)
- [ ] Test `csg dump-templates` raises OutputWriteError for read-only target (AC: 3)

#### test_list_backends_command.py (new)
- [ ] Test `csg list-backends` shows all three backends (AC: 4)
- [ ] Test `csg list-backends` shows availability (AC: 4)
- [ ] Test `csg list-backends` shows parameters with type/default/range (AC: 4)
- [ ] Test `csg list-backends` supports --output-format (AC: 5)

#### test_settings_serializer.py (new)
- [ ] Test serialize handles all AppSettings fields
- [ ] Test serialize output is valid TOML
- [ ] Test serialize handles None Path values
- [ ] Test serialize handles empty tuples

## Dev Notes

### Current State

**Existing ports (Protocols in `ports/`):**
- `ConfigResolverPort` at `ports/config_resolver.py:9` — single method `resolve() -> AppSettings`
- `SettingsSerializerPort` at `ports/settings_serializer.py:9` — `serialize(settings) -> str` and `deserialize(raw) -> AppSettings`
- `BackendCatalogLoaderPort` at `ports/backend_catalog_loader.py:10` — `load() -> dict[Backend, BackendDefinition]`
- `TemplateDirResolverPort` at `ports/template_dir_resolver.py:8` — `resolve() -> Path`
- `VersionProviderPort` at `ports/version_provider.py:7` — `get_version() -> str`

**Existing adapters:**
- `AssembledConfigResolver` at `adapters/settings/config_resolver.py:67`:
  - Implements config resolution via config-assembler-engine
  - Has `last_result: ConfigResolverResult | None` property (populated after `resolve()`)
  - `resolve()` can take `cli_overrides` and `explicit_path`
  - Already catches `ConfigParseError` and `PathResolutionError`, converts to `ConfigResolutionError`
- `YamlBackendCatalogLoader` at `adapters/yaml_backend_catalog_loader.py:62`:
  - `load()` returns `dict[Backend, BackendDefinition]`
  - Catches `ConfigParseError`, `PathResolutionError`, `ConfigValidationError`
- `TemplateDirResolver` at `adapters/template_dir_resolver.py:73`:
  - `resolve()` returns `Path`
  - Uses env var `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` → XDG → package defaults

**NO adapter exists for `SettingsSerializerPort`** — must be created.

**NO adapter exists for `VersionProviderPort`** — not needed for this story (already handled in version_cmd.py via `importlib.metadata.version`).

**Existing `factory.py` (`factory.py:23-62`):**
```python
@dataclass
class CliDependencies:
    backend_registry: BackendRegistry
    backend_catalog_loader: YamlBackendCatalogLoader | None = None
    output_adapter: OutputPort | None = None
    processor: LocalProcessor | None = None
    template_dir_resolver: TemplateDirResolver | None = None
    template_renderer: TemplateRendererPort | None = None
```

Must add:
- `config_resolver: AssembledConfigResolver | None = None`

Existing factory functions to reuse:
- `create_backend_catalog_loader()` at `factory.py:41`
- `create_template_dir_resolver()` at `factory.py:45`
- `create_template_renderer()` at `factory.py:49`
- `create_output_adapter(fmt)` at `factory.py:53`

Must add:
- `create_config_resolver()` → `AssembledConfigResolver()`

**Existing `cli/main.py` (`main.py:31-36`):**
```python
def build_deps() -> CliDependencies:
    registry = create_backend_registry()
    return CliDependencies(
        backend_registry=registry,
        processor=LocalProcessor(registry),
    )
```

Must update to include all deps:
- `backend_catalog_loader=create_backend_catalog_loader()`
- `template_dir_resolver=create_template_dir_resolver()`
- `config_resolver=create_config_resolver()`
- `template_renderer=create_template_renderer()`

**Existing CLI commands registered in `main.py`:**
```python
app.command()(show)
app.command()(version)
```

Add 4 more.

**Existing output adapter pattern (from 2.7):**
- `--output-format` is global in `@app.callback()`, stored in `ctx.obj["deps"].output_adapter`
- Version command uses `isinstance(adapter, JsonOutput/RichOutput/PlainOutput)` pattern at `cli/version_cmd.py:24-29`
- **Follow this pattern** for info/list-backends/dump-config output formatting

**Domain models relevant to this story:**
- `AppSettings` at `domain/models.py:153-158`: composes `OutputSettings`, `GenerationSettings`, `TemplateSettings`, `RuntimeSettings`, `ContainerSettings`
- `ConfigResolverResult` at `domain/models.py:147-149`: `resolved_path: Path`, `applied_overrides: tuple[AppliedOverride, ...]`
- `AppliedOverride` at `domain/models.py:139-143`: `field_path`, `raw_value`, `coerced_value`, `source`
- `BackendDefinition` at `domain/models.py:93-98`: `backend`, `display_name`, `description`, `parameters`, `min_version`
- `BackendParameterDefinition` at `domain/models.py:83-89`: `name`, `type_`, `description`, `required`, `choices`, `default`
- `Backend` enum at `domain/enums.py:6-23`: three members with `install_hint` and `image_suffix` properties

**Exceptions to use:**
- `ConfigResolutionError` at `domain/exceptions.py:42` — for config resolution failures
- `OutputWriteError` at `domain/exceptions.py:35` — for file write failures in dump-config/dump-templates
- `ColorSchemeError` base at `domain/exceptions.py:9` — catch-all for structured error output

**Conventions from previous stories (pre-applied from 2.6/2.7 reviews):**
1. All new exceptions exported from `domain/__init__.py` and `errors.py` (no new exceptions here)
2. No broad `except Exception` — catch specific exceptions only
3. All CLI commands must output structured errors via `deps.output_adapter.error(exc)`
4. Follow Capsys-based test pattern for output adapters
5. Ruff clean required for all new/modified files
6. All ~251 existing tests must pass — zero regressions
7. Use Typer CliRunner for CLI tests
8. Mock adapter dependencies not relevant to the specific command
9. No `Path.home()` at import time — defer to lazy evaluation in function bodies

### TOML Serialization Approach

Since the project has no external TOML writing library, write a simple serializer that converts AppSettings to TOML string manually:

```python
def _value_to_toml(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, Enum):
        return f'"{v.value}"'
    if isinstance(v, Path):
        return f'"{v!s}"'
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, int | float):
        return str(v)
    if isinstance(v, tuple | list):
        return "[]" if not v else "[" + ", ".join(_value_to_toml(x) for x in v) + "]"
    if v is None:
        return ""
    return f'"{v!s}"'
```

For `None` values, skip the key entirely (TOML has no null/None).

### Info Output Format Specification

**JSON format:**
```json
{
  "config_path": "/home/user/.config/color-scheme-generator/settings.toml",
  "config_source": "xdg",
  "applied_overrides": [
    {"field_path": "runtime.mode", "raw_value": "container", "coerced_value": "container", "source": "cli"}
  ],
  "runtime_mode": "local",
  "container_engine": "docker",
  "templates_directory": "/home/user/.config/color-scheme/templates",
  "backends": {
    "custom": {"available": true},
    "pywal": {"available": false},
    "wallust": {"available": false}
  }
}
```

**Plain format:**
```
Config path: /home/user/.config/color-scheme-generator/settings.toml
Config source: xdg
Runtime mode: local
Container engine: docker
Templates directory: /home/user/.config/color-scheme/templates
Backends:
  custom: available
  pywal: not available
  wallust: not available
Overrides:
  runtime.mode = container (source: cli, coerced: container)
```

**Rich format:** Use `rich.table.Table` with sections.

### List-Backends Output Format Specification

**JSON format:**
```json
{
  "backends": [
    {
      "name": "custom",
      "display_name": "Custom",
      "description": "PIL + KMeans extraction",
      "available": true,
      "image_available": null,
      "parameters": [
        {"name": "saturation", "type": "float", "default": 1.0, "range": [0, 2]},
        {"name": "n_clusters", "type": "int", "default": 16, "range": [1, 32]},
        {"name": "algorithm", "type": "str", "default": "kmeans", "choices": ["kmeans"]}
      ]
    }
  ]
}
```

**Plain format:**
```
custom - PIL + KMeans extraction
  Available: yes
  Image: not implemented
  Parameters:
    saturation (float, default: 1.0, range: 0-2)
    n_clusters (int, default: 16, range: 1-32)
    algorithm (str, default: kmeans, choices: kmeans)
```

### Dump-Templates: Bundled template source

Templates are bundled at `color_scheme_generator/defaults/templates/`:
```
colors.json.j2
colors.sh.j2
colors.css.j2
colors.gtk.css.j2
colors.yaml.j2
colors.rasi.j2
colors.scss.j2
colors.sequences.j2
```

Use `importlib.resources.files("color_scheme_generator.defaults").joinpath("templates")` to find them.

Default target: `$XDG_CONFIG_HOME/color-scheme-generator/templates/` (or `~/.config/color-scheme-generator/templates/` if XDG not set).

### Files to create

| File | Action |
|------|--------|
| `src/color_scheme_generator/adapters/settings/settings_serializer.py` | NEW — TOML serializer |
| `src/color_scheme_generator/cli/info_cmd.py` | NEW — info command |
| `src/color_scheme_generator/cli/dump_config_cmd.py` | NEW — dump-config command |
| `src/color_scheme_generator/cli/dump_templates_cmd.py` | NEW — dump-templates command |
| `src/color_scheme_generator/cli/list_backends_cmd.py` | NEW — list-backends command |
| `tests/unit/adapters/settings/test_settings_serializer.py` | NEW — serializer tests |
| `tests/unit/cli/test_info_command.py` | NEW — info command tests |
| `tests/unit/cli/test_dump_config_command.py` | NEW — dump-config tests |
| `tests/unit/cli/test_dump_templates_command.py` | NEW — dump-templates tests |
| `tests/unit/cli/test_list_backends_command.py` | NEW — list-backends tests |

### Files to modify

| File | Changes |
|------|---------|
| `src/color_scheme_generator/factory.py` | Add `config_resolver` to `CliDependencies`, add `create_config_resolver()` |
| `src/color_scheme_generator/cli/main.py` | Import and register 4 new commands, update `build_deps()` to wire all deps |
| `src/color_scheme_generator/adapters/settings/__init__.py` | Export new adapter |

### Test patterns

Follow the existing patterns:
- CLI tests: use Typer `CliRunner` with `runner.invoke(app, [command, args])`
- Mock deps not needed for the command under test (use the full dependency graph)
- `capsys` fixture for stdout capture
- `tmp_path` fixture for file operations in dump-config/dump-templates tests
- Mock `importlib.resources.files()` for dump-templates tests to avoid needing real bundled files
- Mock `is_available()` for backend tests
- Structured output tests: parse JSON and check keys/values

### References

- [Source: epics.md:471-508] Story 2.8 acceptance criteria
- [Source: PRD.md:177-215] FR-10 through FR-13 specs
- [Source: PRD.md:152-163] FR-8 Config resolution spec
- [Source: factory.py] Existing dependency structure
- [Source: ports/settings_serializer.py] SettingsSerializerPort protocol
- [Source: ports/config_resolver.py] ConfigResolverPort protocol
- [Source: ports/backend_catalog_loader.py] BackendCatalogLoaderPort protocol
- [Source: ports/template_dir_resolver.py] TemplateDirResolverPort protocol
- [Source: adapters/settings/config_resolver.py] AssembledConfigResolver implementation
- [Source: adapters/yaml_backend_catalog_loader.py] YamlBackendCatalogLoader implementation
- [Source: adapters/template_dir_resolver.py] TemplateDirResolver implementation
- [Source: domain/models.py] AppSettings, ConfigResolverResult, BackendDefinition, BackendParameterDefinition
- [Source: domain/enums.py] Backend enum
- [Source: cli/version_cmd.py] Output adapter pattern (isinstance dispatch)
- [Source: cli/main.py] Typer app registration pattern
- [Source: defaults/templates/] 8 bundled .j2 template files for dump-templates

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Dev Notes from Previous Story (2.7)

- Output adapter pattern: `isinstance(adapter, JsonOutput/RichOutput/PlainOutput)` for inline formatting
- All ~251 tests must pass — zero regressions
- Ruff clean required for all new/modified files
- Follow established project conventions (no bare exceptions, structured errors)
- Typer CliRunner + capsys for CLI test patterns
- `isinstance` checks on adapter type (from version_cmd.py:24-29) — acceptable pattern for format dispatch where OutputPort lacks a generic method

### Completion Notes

### File List

### New files
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/settings_serializer.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/info_cmd.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/dump_config_cmd.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/dump_templates_cmd.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/list_backends_cmd.py`
- `src/cli-tools/color-scheme-generator/tests/unit/adapters/settings/test_settings_serializer.py`
- `src/cli-tools/color-scheme-generator/tests/unit/cli/test_info_command.py`
- `src/cli-tools/color-scheme-generator/tests/unit/cli/test_dump_config_command.py`
- `src/cli-tools/color-scheme-generator/tests/unit/cli/test_dump_templates_command.py`
- `src/cli-tools/color-scheme-generator/tests/unit/cli/test_list_backends_command.py`

### Modified files
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/factory.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/main.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/__init__.py`
