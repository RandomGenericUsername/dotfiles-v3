## Why

After `cli-flag-scope-refinement` moved `--runtime` and `--container-engine` from root to leaves/sub-typers, three flags remain on the root callback that are not truly cross-cutting: `--config`, `--templates-dir` (CSG), and `--effects` (WEG). These flags configure *which resources the tool reads* (config file, templates dir, effects file) — a per-operation concern, not a universal output/logging concern like `--output-format` or `--verbose`.

Additionally, two pre-existing issues are addressed:

- **CSG `dump-config` behavior diverges from WEG's:** CSG's `dump-config` resolves config + serializes the resolved result, requiring `--config` to be accepted. WEG's `dump-config` simply prints the bundled default template. Aligning them reduces surface and removes `dump-config`'s dependency on `--config`.
- **CSG `install`/`uninstall` ignore `--config`:** They call `config_resolver.resolve()` with no `explicit_path`, ignoring whatever the user passed via `--config`. WEG's equivalents correctly pass `config_path`. This is a bug.

## What Changes

1. **Add shared option factories** (`CONFIG_OPT`, `TEMPLATES_DIR_OPT`, `EFFECTS_OPT`) to both tools' `cli/options.py`.
2. **Scope `--config`** to commands that resolve settings:
   - CSG: `generate`, `show`, `info`, `install`, `uninstall` (leaf options).
   - WEG: `process` sub-typer callback, `batch` sub-typer callback, `info`, `install`, `uninstall` (leaf options for standalone commands; callback options for sub-typers).
3. **Scope `--templates-dir`** (CSG only) to `generate`, `show`, `info` leaf options.
4. **Scope `--effects`/`-e`** (WEG only) to `process` sub-typer callback, `batch` sub-typer callback, `show` sub-typer callback (new), `info` leaf option.
5. **Align CSG `dump-config` with WEG:** replace resolve+serialize with print-bundled-default. `info --config` covers the inspection use case.
6. **Fix CSG `install`/`uninstall` bug:** pass `config_path` to `config_resolver.resolve(explicit_path=...)`.
7. **Add `@show_app.callback()`** to WEG `show.py` declaring `--effects`.
8. **Remove `--config`, `--templates-dir`, `--effects`** from both root callbacks.

**Root callback after (both tools):** only `--output-format`, `--verbose`/`-v`, `--quiet`/`-q` remain. Framework flags (`--help`, `--completion`) are inherent.

## Capabilities

### New Capabilities
- `cli-flag-factories`: Extended with `CONFIG_OPT`, `TEMPLATES_DIR_OPT` (CSG) and `CONFIG_OPT`, `EFFECTS_OPT` (WEG) in `cli/options.py`.

### Modified Capabilities
- `cli-runtime-engine-scope`: Completes the flag-scope refinement. The consumer table now covers ALL root-to-leaf flag moves (`--runtime`, `--container-engine`, `--config`, `--templates-dir`, `--effects`). The root callback is reduced to the truly cross-cutting set.

## Impact

- **CSG CLI (7 files):** `main.py` (root callback loses 2 flags, 4 leaf commands gain flags), `show.py` (gains 2 flags), `info_cmd.py` (gains 2 flags), `install_cmd.py` (gains `--config` + bug fix), `uninstall_cmd.py` (gains `--config` + bug fix), `dump_config_cmd.py` (full rewrite), `options.py` (adds 2 factories).
- **WEG CLI (7 files):** `main.py` (root callback loses 2 flags, 3 leaf commands gain flags), `process.py` (callback gains 2 flags), `batch.py` (callback gains 2 flags), `show.py` (new callback), `info.py` (gains 2 flags), `install.py`/`uninstall.py` (gains `--config`; already passes config_path).
- **Tests:** Flag-position assertions update across both tool test suites. New regression tests for CSG `install`/`uninstall` `--config` wiring.
- **CI/Scripts:** Any CI or user scripts passing `--config`, `--templates-dir`, or `--effects` as global flags (before command name) must reposition them after the command name.
