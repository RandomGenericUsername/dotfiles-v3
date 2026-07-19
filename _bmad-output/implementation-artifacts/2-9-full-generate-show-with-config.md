---
baseline_commit: 0174e40
---

# Story 2.9: Full Generate/Show with Config, Backends, Formats

Status: ready-for-dev

## Story

As a theming user,
I want `csg generate` and `csg show` to use my settings.toml, selected backend, and output formats,
So that the tool respects my configuration instead of using hardcoded defaults.

## Acceptance Criteria

### AC 1: Config-driven generate

**Given** the config resolution pipeline (2.2)
**When** `csg generate ~/wallpaper.jpg` is run
**Then** it resolves settings.toml via deps.config_resolver.resolve()
**And** uses settings.generation.backend as the default backend (instead of hardcoded Backend.CUSTOM)
**And** uses settings.generation.default_formats for output formats
**And** writes rendered template files to settings.output.directory
**And** respects settings.output.overwrite flag

### AC 2: --backend flag on generate

**Given** the --backend flag
**When** `csg generate --backend pywal ~/wallpaper.jpg` is run
**Then** it overrides the configured default backend
**When** `csg generate --backend invalid ~/wallpaper.jpg` is run
**Then** it raises a validation error with accepted values (via Typer enum validation — Backend enum already has click-like type conversion; if Typer doesn't auto-validate, use a callback)
**When** `--backend` is omitted
**Then** the default from settings.generation.backend is used

### AC 3: --param flag on generate

**Given** the --param flag
**When** `csg generate --param saturation=1.5 --param algorithm=thief ~/wallpaper.jpg` is run
**Then** it parses params via _parse_params helper
**And** coerces values via ParameterResolutionService (from story 2.1)
**And** passes resolved params to GeneratorConfig.params
**When** `--param bogus=1` is passed for a backend without that param
**Then** it raises ConfigResolutionError
**When** `--param badformat` (no `=`) is passed
**Then** it's silently ignored (per PRD FR-3)

### AC 4: -f / --format flag on generate

**Given** the -f / --format flag
**When** `csg generate -f json -f css ~/wallpaper.jpg` is run
**Then** only those formats are rendered
**When** no -f flag is passed
**Then** settings.generation.default_formats are used
**When** an invalid format value is passed
**Then** Typer validation rejects it (use ColorFormat enum)

### AC 5: -o / --output-dir flag on generate

**Given** the -o / --output-dir flag
**When** `csg generate -o ~/my-theme ~/wallpaper.jpg` is run
**Then** output files are written to ~/my-theme
**When** -o is omitted
**Then** settings.output.directory is used

### AC 6: All backends unavailable handling

**Given** all backends are unavailable in local mode (is_available() returns False for all)
**When** `csg generate ~/wallpaper.jpg` is run
**Then** it raises BackendNotAvailableError with a message suggesting `csg install` or installing the binary
**And** the error is surfaced before any extraction attempt

### AC 7: show command parity

**Given** the show command
**When** `csg show --backend pywal --param saturation=1.5 ~/wallpaper.jpg` is run
**Then** it respects --backend, --param, --output-format flags the same as generate
**And** does NOT accept -f/--format or -o/--output-dir (show doesn't write files)

## Tasks / Subtasks

### CLI: Update generate in main.py (existing)
- [ ] Import and use deps.config_resolver.resolve() to get AppSettings (AC: 1)
- [ ] Add --backend flag: `backend: Backend = typer.Option(None, "--backend", help="Extraction backend")` (AC: 2)
- [ ] Add --param flag: `param: list[str] = typer.Option([], "--param", help="Backend parameter overrides")` (AC: 3)
- [ ] Add -f / --format flag: `formats: list[ColorFormat] = typer.Option(None, "--format", "-f", help="Output formats")` (AC: 4)
- [ ] Add -o / --output-dir flag: `output_dir: Path = typer.Option(None, "--output-dir", "-o", help="Output directory")` (AC: 5)
- [ ] Implement _parse_params helper: parse "key=value" strings into dict[str, str] (AC: 3)
- [ ] Implement param resolution logic: use ParameterResolutionService if available (AC: 3)
- [ ] Implement backend resolution: CLI flag > settings.generation.backend (AC: 2)
- [ ] Implement format resolution: CLI flags > settings.generation.default_formats (AC: 4)
- [ ] Implement output dir resolution: CLI flag > settings.output.directory (AC: 5)
- [ ] Add all-backends-unavailable check before extraction (AC: 6)
- [ ] Wire resolved config into GenerationRequest and LocalProcessor.process_generate (AC: 1)

### CLI: Update show in show.py (existing)
- [ ] Add --backend flag (same semantics as generate) (AC: 7)
- [ ] Add --param flag (same semantics as generate) (AC: 7)
- [ ] Use deps.config_resolver.resolve() for settings (AC: 7)
- [ ] Implement backend resolution (AC: 7)
- [ ] Add all-backends-unavailable check before extraction (AC: 7)

### CLI: Wire show into main.py (existing)
- [ ] Ensure show command's additional flags are properly registered (AC: 7)

### Write tests (extend existing or create new)
- [ ] Test generate with --backend flag overrides default (AC: 2)
- [ ] Test generate with --backend invalid raises error (AC: 2)
- [ ] Test generate with --param key=value overrides (AC: 3)
- [ ] Test generate with --param bogus raises ConfigResolutionError (AC: 3)
- [ ] Test generate with --param badformat (no =) is silently dropped (AC: 3)
- [ ] Test generate with -f json -f css only renders those (AC: 4)
- [ ] Test generate with -o custom-dir writes there (AC: 5)
- [ ] Test generate without -o uses settings.output.directory (AC: 5)
- [ ] Test generate with no backends available raises BackendNotAvailableError (AC: 6)
- [ ] Test generate resolves config via AssembledConfigResolver (AC: 1)
- [ ] Test show accepts --backend and --param (AC: 7)
- [ ] Test show rejects -f and -o flags (AC: 7)

## Dev Notes

### Current State

**cli/main.py** currently hardcodes all settings in the `generate` function (lines 65-114):
```python
config = GeneratorConfig(
    backend=Backend.CUSTOM,
    params={},
    formats=(),
    output_dir=Path("/tmp/color-scheme"),
)
settings = AppSettings(
    output=OutputSettings(directory=Path("/tmp/color-scheme"), ...),
    generation=GenerationSettings(backend=Backend.CUSTOM, ...),
    ...
)
```

This must be replaced with real config resolution and CLI flags.

**cli/show.py** has the same hardcoded pattern (lines 26-59).

**factory.py** already has `config_resolver: AssembledConfigResolver | None = None` in `CliDependencies` and `create_config_resolver()` factory function. `build_deps()` in main.py already wires it with `config_resolver=create_config_resolver()`.

**Processor architecture:**
- `LocalProcessor.process_generate(request, settings)` already exists — takes `GenerationRequest` and `AppSettings`
- `GenerationRequest` has `image_path` and `config: GeneratorConfig`
- `GeneratorConfig` has `backend`, `params`, `formats`, `output_dir`
- The `settings` object is used for template rendering, output paths, etc.

**ParameterResolutionService** from story 2.1 at `domain/services.py`:
- `resolve_all(parameters: tuple[BackendParameterDefinition, ...], overrides: dict[str, str]) -> dict[str, Any]`
- Returns override values where present, defaults otherwise
- Raises ConfigResolutionError if a required param has no default and no override
- The backend's parameter definitions come from the YAML catalog via `deps.backend_catalog_loader.load()`

**Backend availability check:**
- `deps.backend_registry[backend].is_available()` for each Backend
- CustomGenerator checks PIL+sklearn import
- PywalGenerator checks `wal` on PATH
- WallustGenerator checks `wallust` on PATH

**Typer enum validation:**
- Typer auto-converts string args to enum members if the type hint is an Enum class
- For `Backend` enum, passing "invalid" will raise a `typer.BadParameter` error with accepted values
- For `ColorFormat` enum, same behavior

**Output adapter already in place:**
- `--output-format` is a global callback option (from 2.7)
- `deps.output_adapter` is set in `@app.callback()` before any command runs
- No changes needed for output format in this story

**Existing CLI patterns to follow:**
- Generate command at `main.py:65-114` — follow its try/except pattern
- Show command at `show.py:21-69` — similar pattern
- All CLI commands use `ctx: typer.Context` and `deps: CliDependencies = ctx.obj["deps"]`

**Backend YAML catalog loading:**
- `deps.backend_catalog_loader.load()` returns `dict[Backend, BackendDefinition]`
- Each `BackendDefinition` has `parameters: tuple[BackendParameterDefinition, ...]`
- needed for ParameterResolutionService to resolve param overrides

### _parse_params helper

Create a standalone function (either in a new `cli/params.py` or inline in the command) that:
- Splits each string on first `=`
- If no `=` found: silently skip (per PRD FR-3: "Malformed entries (no `=`) are silently dropped")
- Returns `dict[str, str]` of key-value pairs
- Handles multiple values for same key: last wins

```python
def _parse_params(raw: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in raw:
        if "=" not in entry:
            continue
        key, _, value = entry.partition("=")
        result[key.strip()] = value.strip()
    return result
```

### Architecture Compliance

- Must use existing `ConfigResolverPort` via `deps.config_resolver`
- Must use existing `BackendCatalogLoaderPort` via `deps.backend_catalog_loader` for parameter definitions
- Must use `ParameterResolutionService` from `domain/services.py` for param coercion
- Must preserve NFR-2: errors always produce structured JSON via `deps.output_adapter.error(exc)`
- All CLI flags must follow Typer conventions (typed, with help text)
- Backend resolution: CLI `--backend` > settings.generation.backend > Backend.CUSTOM (fallback if no config)

### Previous Story Intelligence (from 2.8)

- **Factory pattern**: `CliDependencies` has `config_resolver`, `backend_catalog_loader`, `template_dir_resolver` all wired
- **Config resolution**: `config_resolver.resolve()` returns `AppSettings` or raises `ConfigResolutionError`
- **Error pattern**: Catch `ColorSchemeError` → `deps.output_adapter.error(exc)` → `raise typer.Exit(code=1)`
- **Test patterns**: Typer CliRunner with `runner.invoke(app, [...])`, mock deps via monkeypatch on `build_deps`
- **Ruff**: Must be clean for all new/modified files
- **All ~298 existing tests must pass** — zero regressions
- Test count target: ~20+ new or updated tests

### Files to create

| File | Action |
|------|--------|
| `tests/unit/cli/test_generate_full.py` or extend existing test_generate.py | NEW/EXTEND — tests for new flags |

### Files to modify

| File | Changes |
|------|---------|
| `src/color_scheme_generator/cli/main.py` | Add --backend, --param, -f, -o flags to generate; use config_resolver |
| `src/color_scheme_generator/cli/show.py` | Add --backend, --param flags; use config_resolver |

### File naming convention

Tests should follow the existing pattern: `tests/unit/cli/test_{command}.py`

### References

- [Source: epics.md#509-547] — Story 2.9 acceptance criteria
- [Source: PRD.md#57-103] — FR-1, FR-2, FR-3 Palette Extraction, Backend Selection, Params
- [Source: PRD.md#95-103] — FR-4 Show command details
- [Source: domain/services.py] — ParameterResolutionService.resolve_all()
- [Source: domain/models.py] — AppSettings, GeneratorConfig, GenerationRequest
- [Source: domain/enums.py] — Backend, ColorFormat enums
- [Source: cli/main.py] — Current generate command (to modify)
- [Source: cli/show.py] — Current show command (to modify)
- [Source: factory.py] — CliDependencies, create_config_resolver()
- [Source: adapters/settings/config_resolver.py] — AssembledConfigResolver
- [Source: adapters/yaml_backend_catalog_loader.py] — YamlBackendCatalogLoader
