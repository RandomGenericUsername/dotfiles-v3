## 1. Resolution-layer expansion (cli/main.py)

- [x] 1.1 In `generate`, the `else` branch (no `-f/--format`): when `settings.output.default_formats` is empty and `deps.template_catalog_loader is not None`, load the catalog via `load(explicit_dir=templates_dir)` and derive `default_formats = tuple(t.format for t in catalog.templates)` before building `resolved_formats`
- [x] 1.2 Do NOT wrap the loader call in a local `try/except ... raise typer.Exit`; let `ColorSchemeError` propagate to the existing `except ColorSchemeError` handler (avoids double error emission from the broad `except Exception`)

## 2. Fallback defaults (cli/_helpers.py)

- [x] 2.1 Change `default_app_settings().output.default_formats` from `()` to `(ColorFormat.JSON, ColorFormat.SH)`
- [x] 2.2 Add `ColorFormat` to the enum import in `cli/_helpers.py`

## 3. Docs & defaults

- [x] 3.1 Add comment to `defaults/settings.toml` documenting empty-means-all: `# Leave empty [] to render every template found in the templates directory.`
- [x] 3.2 Update `docs/ARCHITECTURE_PLAN.md` `-f` default note to `settings.output.default_formats; empty => all loaded templates`

## 4. Tests

- [x] 4.1 Add `_deps_with_loader` helper in `tests/unit/cli/test_generate_full.py` wiring a fake `template_catalog_loader` returning a catalog of given formats
- [x] 4.2 New `TestGenerateEmptyDefaultFormats` suite:
  - empty `default_formats` + loader → recorded `config.formats` equals all catalog formats (order preserved)
  - explicit `-f` bypasses expansion and the loader is not called
  - non-empty `default_formats` wins over catalog; loader not called
  - empty `default_formats` + `template_catalog_loader=None` → formats stay empty, exit 0
  - loader raising `TemplatesValidationError` → exit 1, typed error `TemplatesValidationError`
  - `--templates-dir` with empty `default_formats` → loader called with `explicit_dir` set to that dir
- [x] 4.3 Update `test_output_dir_flag_writes_there` to use a writable `tmp_path` (fallback now renders `json`+`sh`)

## 5. Verification

- [x] 5.1 Run `uv run pytest tests/unit -q` from `src/cli-tools/color-scheme-generator` — all green (550 passed)
- [x] 5.2 Run `uv run ruff check src tests` — only pre-existing violations remain (none in changed lines)
- [x] 5.3 Run `uv run ruff format --check tests/unit/cli/test_generate_full.py` — clean
- [x] 5.4 Manual smoke test: `default_formats = []` + 4 templates → 4 files; `default_formats = ["json"]` → 1 file; `-f css -f rasi` → those 2
