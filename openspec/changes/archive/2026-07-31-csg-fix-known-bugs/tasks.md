# CSG Fix Known Bugs — Tasks

## 1. Validate `default_formats` in the settings schema (Bug 1)
- [x] 1.1 Add `_VALID_FORMATS = {m.value for m in ColorFormat}` and a `@field_validator("default_formats")` to `OutputSettingsSchema` (`adapters/settings/schema.py`) that raises `ValueError` for any entry not in `_VALID_FORMATS`; import `ColorFormat`.
- [x] 1.2 Keep field type `list[str]` (validate-not-coerce) so `test_schema.py` `["json","sh"]` equality still holds.

## 2. Thread `min_version` through the catalog schema and loader (Bug 3)
- [x] 2.1 Add `min_version: str = "0.0.0"` to `BackendDefinitionSchema` (`adapters/schemas/backends_catalog_schema.py`).
- [x] 2.2 Replace `min_version="0.0.0"` with `min_version=def_schema.min_version` in `_schema_to_domain` (`adapters/yaml_backend_catalog_loader.py`).

## 3. Rewrite `--help` to list all 5 config strategies (Bug 4)
- [x] 3.1 Update the `typer.Typer(help=...)` string in `cli/main.py`: add `1. --config flag` and renumber 2-5, mirroring the resolver chain. Leave the templates block and ENV-overrides line unchanged.

## 4. Route the 4 commands through `OutputPort` (Bug 5-8)
- [x] 4.1 Add `install_result`/`uninstall_result`/`version_info`/`backends_catalog` signatures to the `OutputPort` Protocol (`ports/output.py`).
- [x] 4.2 Implement the 4 methods on `JsonOutput` (`adapters/output/json_output.py`) by moving the inline JSON-rendering code.
- [x] 4.3 Implement the 4 methods on `PlainOutput` (`adapters/output/plain_output.py`).
- [x] 4.4 Implement the 4 methods on `RichOutput` (`adapters/output/rich_output.py`).
- [x] 4.5 Replace `isinstance` dispatch with a single `adapter.<method>(...)` call in `cli/install_cmd.py`, `cli/uninstall_cmd.py`, `cli/version_cmd.py`, `cli/list_backends_cmd.py`; drop now-unused imports.

## 5. Convert the 8 xfails to real tests and harden pytest
- [x] 5.1 Remove the 2 xfail decorators in `tests/unit/adapters/settings/test_schema.py` (rename `TestKnownBugsXfail` → `TestDefaultFormatsValidation`).
- [x] 5.2 Remove the 1 xfail decorator in `tests/unit/adapters/test_yaml_backend_catalog_loader.py` (rename → `TestMinVersionRoundTrip`).
- [x] 5.3 Remove the 5 xfail decorators in `tests/unit/cli/test_known_bugs.py`; add the 4 new port methods to `_RecordingOutputAdapter` so the routing tests pass.
- [x] 5.4 Add the 4 new methods to `MockOutput` in `tests/unit/ports/test_interfaces.py` so the structural `isinstance` check still passes.
- [x] 5.5 Add `addopts = ["--strict-markers", "-rxX"]` to `pyproject.toml` `[tool.pytest.ini_options]`.

## 6. Verify
- [x] 6.1 `uv run pytest -q` — 544 passed, 0 xfailed.
- [x] 6.2 `uv run ruff check .` — only the 29 pre-existing errors (unchanged from baseline); no new findings in edited files.
- [x] 6.3 Manual CLI: `csg --help` lists 5 strategies; `csg list-backends` renders in json/rich/plain; `csg install --dry-run`/`csg uninstall --dry-run --yes`/`csg version` render identical JSON payloads to baseline.
- [x] 6.4 Ad-hoc assertions: `default_formats=["weird"]` raises `ValidationError`; YAML `min_version: "1.2.3"` round-trips.

## 7. OpenSpec artifact
- [x] 7.1 Create `openspec/changes/2026-07-31-csg-fix-known-bugs/` with proposal.md, design.md, tasks.md, and spec deltas (Modified `csg-cli-integration-tests` + `help-text-display`; New `csg-output-port-routing` + `csg-settings-schema-validation` + `csg-backend-catalog-min-version`).
- [x] 7.2 Archive the change when approved.