# CSG Fix Known Bugs

## Why

The `csg` (color-scheme-generator) test suite carries 8 `@pytest.mark.xfail` markers introduced by the archived `2026-07-31-csg-test-characterization` change (task §8, "flag, don't fix"). Each xfail documents a real behavioral defect but asserts the *desired* behavior, so the suite never locks the module's *actual* contract. Worse, every xfail uses `strict=False` with no `--strict-markers`/`-rxX`/CI gate, so an accidental fix would silently report `XPASSED` and exit 0 — the tripwire is unplugged and stale xfails rot undetected.

Four distinct defects hide behind the 8 xfails:

1. **`default_formats` is unvalidated** — `OutputSettingsSchema.default_formats` is declared `list[str]` with no validator; arbitrary strings (`"weird"`) are accepted at the schema boundary and only fail late in `cli/main.py` when `ColorFormat(f)` is finally called. 2 xfails.
2. **`min_version` is hardcoded** — `YamlBackendCatalogLoader._schema_to_domain` stamps `min_version="0.0.0"` on every `BackendDefinition` regardless of YAML, and `BackendDefinitionSchema` has no `min_version` field so pydantic silently drops the key. 1 xfail.
3. **`--help` omits the `--config` step** — the hand-written help string in `cli/main.py` lists 4 config-discovery steps, but the real resolver chain has 5 (`CliPathStrategy` for `--config` is first). The CLI advertises a contract it doesn't honor. 1 xfail.
4. **4 commands bypass `OutputPort`** — `install`, `uninstall`, `version`, `list-backends` reach the user via `if isinstance(adapter, JsonOutput/RichOutput/PlainOutput): print(...)` chains that call adapter-private methods or `print()` directly, never the `OutputPort` abstraction. A 3rd-party adapter implementing only `OutputPort` would produce nothing from these commands. 4 xfails.

## What Changes

- **Validate `default_formats`** against the `ColorFormat` enum *values* in `OutputSettingsSchema` via a `field_validator`. The field stays `list[str]` (validate-not-coerce) so the serializer keeps ownership of enum coercion and `test_schema.py`'s `["json","sh"]` equality still holds. Invalid strings raise `ValidationError` at the schema boundary.
- **Thread `min_version`** through `BackendDefinitionSchema` (add `min_version: str = "0.0.0"` — backward compatible) and replace the hardcoded `"0.0.0"` in `_schema_to_domain` with `def_schema.min_version`. Existing YAMLs without the key stay `"0.0.0"`; declared values round-trip.
- **Rewrite `--help`** so the settings discovery list mirrors the resolver chain: `1. --config flag` → `2. COLORSCHEME_CONFIG_FILE_PATH env var` → `3. settings.toml in CWD or up to 3 parent levels` → `4. XDG default` → `5. Package-bundled defaults`.
- **Extend `OutputPort`** with 4 named methods (`install_result`, `uninstall_result`, `version_info`, `backends_catalog`), matching the existing `process_result`/`palette_display`/`config_info` named-method convention. Implement each on `JsonOutput`, `RichOutput`, `PlainOutput` (moving the inline `print`/`Table` code out of the command files into adapter methods). Replace the `isinstance` dispatch blocks in the 4 command files with a single `adapter.<method>(...)` call. **BREAKING** for any out-of-tree `OutputPort` implementation (none exist in this repo) — they must add the 4 methods.
- **Remove all 8 `@pytest.mark.xfail` decorators** — the tests now pass as real characterization tests locking the module's actual (now-correct) contract.
- **Add `--strict-markers -rxX`** to `pyproject.toml` `[tool.pytest.ini_options] addopts` so any future xfail misuse or stale-xfail `XPASS` trips CI.

### Out of scope

The mock-heavy `install`/`uninstall`/`list-backends`/`info`/`dump-*` tests that assert `mock.build_image.call_count == N` keep passing unchanged — they mock the container engine, not the output port, and rewriting them to observable-output assertions is a separate follow-up change. The 4 bug fixes here do not require touching those tests.

## Capabilities

### Modified Capabilities
- `csg-cli-integration-tests`: add a requirement that `install`/`uninstall`/`version`/`list-backends` route their results through the `OutputPort` abstraction (not `isinstance` dispatch on concrete adapters).
- `help-text-display`: add a requirement that `csg --help` lists all 5 config-discovery strategies including the `--config` flag.

### New Capabilities
- `csg-output-port-routing`: define the 4 new `OutputPort` methods and assert that the 4 commands route through them with a `_RecordingOutputAdapter` that implements only the port interface.
- `csg-settings-schema-validation`: `OutputSettingsSchema.default_formats` rejects any string not in `ColorFormat` enum values; validates at both the nested and `CoreSettingsSchema` levels.
- `csg-backend-catalog-min-version`: `BackendDefinitionSchema.min_version` round-trips a YAML-declared value into `BackendDefinition.min_version`; default `"0.0.0"` preserved when absent.

## Impact

All changes are in the CSG module at `src/cli-tools/color-scheme-generator/`. No changes to shared `oci-runtime`/`config-assembler-engine` libraries, no new external dependencies, no container images built or modified.

### Source files
- **Modify**: `adapters/settings/schema.py` (default_formats validator), `adapters/schemas/backends_catalog_schema.py` (min_version field), `adapters/yaml_backend_catalog_loader.py` (pass min_version), `cli/main.py` (help string), `ports/output.py` (4 method signatures), `adapters/output/{json,plain,rich}_output.py` (4 method impls each), `cli/{install,uninstall,version,list_backends}_cmd.py` (replace isinstance dispatch).
- **No change**: domain models, ports other than `output.py`, adapters other than listed, factory, shared libraries.

### Test files
- **Update**: `tests/unit/adapters/settings/test_schema.py` (remove 2 xfails), `tests/unit/adapters/test_yaml_backend_catalog_loader.py` (remove 1 xfail), `tests/unit/cli/test_known_bugs.py` (remove 5 xfails, add 4 new methods to recording adapter), `tests/unit/ports/test_interfaces.py` (add 4 methods to `MockOutput`), `pyproject.toml` (addopts).