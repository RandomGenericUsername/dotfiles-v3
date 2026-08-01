## Context

`csg generate` builds its output-format set in `cli/main.py`. When no `-f/--format` flag is supplied, it copies `settings.output.default_formats` verbatim into `GeneratorConfig.formats`. The bundled `defaults/settings.toml` ships `default_formats = ["json", "sh"]`, but the schema default is `[]`, so any user config that omits the key (or sets it empty) resolves to an empty tuple → `LocalProcessor._render_formats` iterates nothing → a "successful" run with zero output files. The loaded template catalog (`DirectoryTemplateCatalogLoader` → `TemplateCatalogService.derive`) is already the canonical source of "renderable formats": it produces one `ColorSchemeTemplate` per `colors.<fmt>.j2` in the resolved templates directory, and `info` already surfaces it.

## Goals / Non-Goals

**Goals:**
- Empty `output.default_formats` (with no `-f/--format`) resolves to every format present in the loaded templates directory.
- Non-empty `default_formats` and explicit `-f/--format` flags behave exactly as today.
- Catalog load failures surface as typed errors (not silent empty renders).
- Keep the config-resolution-failed fallback safe: it must not suddenly render the full catalog.
- No schema change; `default_formats = []` remains a valid config value.

**Non-Goals:**
- No magic `"all"`/`"*"` sentinel values in `default_formats` (rejected in design review — type pollution, ambiguous mixing semantics, env-override hazards).
- No mutation of `settings.output.default_formats`; expansion happens only on the resolved `GeneratorConfig.formats` at the CLI resolution layer.
- No change to `show` (it hardcodes `formats=()` and does not render templates).
- No change to the serializers or the schema validator.

## Decisions

### D1. Empty-list-means-all at the CLI resolution layer
Expansion lives in `cli/main.py` `generate`, in the `else` branch (no `-f/--format`):
```python
else:
    default_formats = settings.output.default_formats
    if not default_formats and deps.template_catalog_loader is not None:
        catalog = deps.template_catalog_loader.load(explicit_dir=templates_dir)
        default_formats = tuple(t.format for t in catalog.templates)
    resolved_formats = tuple(
        ColorFormat(f) if isinstance(f, str) else f for f in default_formats
    )
```
Rationale: empty is the natural "no preference" signal — a homogeneous list of real `ColorFormat` values with zero new syntax, zero new fields, and zero new validation paths. The catalog (file-derived) is the source of truth for "all", so users who prune their templates dir only get formats that actually render. Alternative considered: a `list[str] | "all"` union or an `all_formats` boolean — rejected (sentinel/type pollution, extra field + precedence rules, env-var awkwardness).

### D2. Null-guard on the loader
Expansion is conditional on `deps.template_catalog_loader is not None`. When it is `None` (injected-processor tests, or any deployment without a catalog loader), prior behavior is preserved: `default_formats` is used as-is, including empty. Rationale: `CliDependencies.template_catalog_loader` is `Optional`; an unconditional `.load()` on `None` raises `AttributeError` → generic `{"error": "unexpected error"}` exit 1, breaking every fixture that omits the loader and providing no degradation path.

### D3. Catalog load failures propagate to the typed error handler
The loader call is intentionally **not** wrapped in a local `try/except ColorSchemeError ... raise typer.Exit`. A naive inline `raise typer.Exit(code=1)` inside the `generate` `try` block is caught by the broad `except Exception` handler (since `typer.Exit` is an `Exception`), producing a double error emission. Instead the `ColorSchemeError` (e.g. `TemplatesValidationError`, `ConfigResolutionError`) propagates to the existing `except ColorSchemeError` handler at the bottom of `generate`, which routes it through `output_adapter.error` and exits 1. This reuses the established error path with no new handling.

### D4. Fallback defaults become `(JSON, SH)`
`cli/_helpers.py::default_app_settings()` returns `default_formats=(ColorFormat.JSON, ColorFormat.SH)` instead of `()`. Rationale: this is the settings used when config resolution fails (`main.py` `except ColorSchemeError` → `default_app_settings()`). With `()` it would trigger D1 expansion on the failure path (render the full catalog into `/tmp/color-scheme`); pinning the two canonical formats keeps the fallback bounded and matches the bundled `settings.toml` / `dump_config` output. Trade-off: the fallback now writes `json`+`sh` instead of nothing — accepted and documented as a minor breaking change.

### D5. `show` is not routed through expansion
`show` keeps its hardcoded `formats=()` literal and never consults `settings.output.default_formats`; it is a preview that does not render template files. Any future shared resolution helper must keep an explicit opt-out (a literal empty tuple), but no shared helper is introduced in this change.

### D6. No serializer changes
Expansion produces `GeneratorConfig.formats` (request-level); `settings.output.default_formats` is never mutated. Therefore `SettingsSerializer` and `ContainerProcessor._serialize_settings` remain unchanged and continue to emit `default_formats = []` for genuinely-empty configs. The container path works automatically: the expanded formats flow into `request.config.formats` and `ContainerProcessor` replays them as explicit `--format` flags in the inner `csg generate`, which bypasses the mounted settings' empty list.

## Risks / Trade-offs

- **Config-resolution-failed fallback now renders `json`+`sh` (was nothing)** → Mitigation: D4 bounds it to the two canonical formats and aligns with bundled defaults; warning message still emitted.
- **`None` loader silently keeps empty formats** → Accepted: D2 is a deliberate degradation path; production `build_deps()` always wires the loader.
- **A missing/invalid templates dir turns a previously-silent empty render into a typed exit-1 error** → Accepted: D3 surfaces the real cause instead of silently "succeeding" with no output; error message names the invalid format(s).
- **Ordering with `resolve_backend_params`** → `parse_params`/`resolve_backend_params` run before the format-resolution block; a bogus `--param` still raises `ConfigResolutionError` before any catalog load, preserving existing error precedence.
- **Empty list is now meaningful** → A config that intentionally wants "render nothing" can no longer express that via `default_formats = []`; workaround: omit templates for all formats, or pass `-f` with no values is not supported — note: this is the intended semantics change and is documented in `settings.toml`.

## Migration Plan

Single-step code change; no data migration. Users with `default_formats = []` who relied on silent no-op renders now get all formats (or a typed error if the catalog fails to load). Rollback: revert the commit; prior behavior (empty → no render) returns.
