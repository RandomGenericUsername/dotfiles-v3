## Why

The `csg` CLI resolves the set of output formats for `csg generate` from `settings.output.default_formats` when no `-f/--format` flag is given. If that setting is empty (`[]` or omitted — the schema defaults to `[]`), the CLI currently renders **zero** output files while still reporting success. Users who want "everything available" must enumerate every format explicitly. The intended capability is: an empty `default_formats` list means "use all formats available in the loaded templates directory", so a user can opt out of pinning formats and get every renderable output.

## What Changes

- **Empty `default_formats` expands to all loaded templates** — In `cli/main.py` `generate`, when no `-f/--format` flag is provided and `settings.output.default_formats` is empty, the resolved format list is derived from the loaded template catalog (`deps.template_catalog_loader.load(explicit_dir=templates_dir).templates`). Non-empty `default_formats` and explicit `-f/--format` flags are unchanged. The catalog respects `--templates-dir`, matching how the renderer already uses it.
- **Null-guard on the loader** — Expansion only runs when `deps.template_catalog_loader is not None`. When no loader is available, the prior behavior is preserved (empty formats remain empty), which also keeps injected-processor and unit-test fixtures stable.
- **Catalog load failures surface as typed errors** — A `ColorSchemeError` raised by the catalog loader (e.g. `TemplatesValidationError`) propagates through the existing `except ColorSchemeError` handler in `generate` → typed error output and exit 1, instead of the previous silent empty render.
- **Emergency fallback defaults** — `cli/_helpers.py::default_app_settings()` now returns `default_formats=(ColorFormat.JSON, ColorFormat.SH)` instead of `()`. This keeps the config-resolution-failed fallback from ballooning into "render every template" and aligns it with the bundled `defaults/settings.toml` and `dump_config`. **BREAKING**: a failed config resolution previously produced zero output files; it now produces the two canonical formats.
- **Docs & defaults** — A comment in `defaults/settings.toml` documents the empty-means-all rule; `docs/ARCHITECTURE_PLAN.md` updates the `-f` default description.

## Capabilities

### New Capabilities
- `csg-default-formats-empty-expansion`: empty `output.default_formats` in `csg` settings resolves to all formats available in the loaded templates directory when no `-f/--format` flag is given, with a null-guarded catalog loader and typed error propagation on catalog load failure.

### Modified Capabilities
- (none — `csg-settings-schema-validation` covers schema validation only; empty lists remain valid there.)

## Impact

- **Source files**:
  - `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/main.py` — `generate`: empty `default_formats` expands to catalog formats when a loader is present.
  - `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/_helpers.py` — `default_app_settings()` returns `(ColorFormat.JSON, ColorFormat.SH)`.
  - `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/settings.toml` — comment documenting empty-means-all.
  - `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md` — `-f` default note.
- **Tests**:
  - `tests/unit/cli/test_generate_full.py` — new `TestGenerateEmptyDefaultFormats` suite (expansion, `-f` bypass, non-empty wins, null-guard, load-failure typed error, `--templates-dir` propagation); `test_output_dir_flag_writes_there` uses a writable `tmp_path` because the fallback now renders `json`+`sh`.
- **Behavior**: `csg generate` with `default_formats = []` (or omitted) renders every template in the templates directory; `csg generate` after a config-resolution failure renders `json`+`sh` instead of nothing.
