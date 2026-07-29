# CLI Runtime & Engine Scope

## Decision

Scope `--runtime` and `--container-engine` to exactly the command tree that consumes them, following the principle: a flag's declaration scope must match its set of actual consumers.

### Scoping strategy

| Flag | Scope | Consumers |
|------|-------|-----------|
| `--runtime` | Sub-typer callbacks (WEG `process`, `batch`); leaf option (CSG `generate`) | CSG `generate`, WEG `process/*`, WEG `batch/*` |
| `--container-engine` | Leaf options on every consumer command | CSG `generate`, CSG `install`, CSG `uninstall`, WEG `process/*`, WEG `batch/*`, WEG `install`, WEG `uninstall` |

### Shared option factories

Each tool provides `cli/options.py` exporting `RUNTIME_OPT` and `ENGINE_OPT` (both `typer.Option` instances defaulting to `None`). Leaf commands import these rather than re-declaring options inline.

### `None` defaults

Both flags default to `None` (optional). A non-None default (like CSG's previous `RuntimeMode.LOCAL`) makes TOML/ENV settings unreachable because the CLI flag always wins. With `None`, omitting the flag means "don't override" and TOML/ENV values are used as-is.

### Lazy processor construction (CSG)

CSG no longer builds a processor in the root callback or as a dependency default. The `generate` command builds it on demand from resolved `--runtime` and `--container-engine` values, matching WEG's existing `_resolve_processor()` pattern.

### WEG `cli_overrides` plumbing activated

WEG's `AssembledConfigResolver.resolve()` now accepts a `cli_overrides` parameter. The `process`/`batch` sub-typer callbacks build the `cli_overrides` dict from parsed flags and pass it to `resolve()` instead of post-resolution object mutation.

### Redundant WEG process options removed

The `-e`/`--effect`, `-c`/`--composite`, `-p`/`--preset` override options on `process effect|composite|preset` are removed — the positional `name` argument already carries the value.

## Final shape

### CSG

| Command | `--runtime` | `--container-engine` |
|---------|:-----------:|:--------------------:|
| `csg generate` | ✅ | ✅ |
| `csg show` | ❌ | ❌ |
| `csg install` | ❌ | ✅ |
| `csg uninstall` | ❌ | ✅ |
| `csg info` | ❌ | ❌ |
| `csg version` | ❌ | ❌ |
| `csg dump-config` | ❌ | ❌ |
| `csg dump-templates` | ❌ | ❌ |
| `csg list-backends` | ❌ | ❌ |

### WEG

| Command | `--runtime` | `--container-engine` |
|---------|:-----------:|:--------------------:|
| `weg process` (sub-typer) | ✅ | ✅ |
| `weg batch` (sub-typer) | ✅ | ✅ |
| `weg install` | ❌ | ✅ |
| `weg uninstall` | ❌ | ✅ |
| `weg info` | ❌ | ❌ |
| `weg version` | ❌ | ❌ |
| `weg show *` | ❌ | ❌ |
| `weg dump-config` | ❌ | ❌ |
| `weg dump-effects` | ❌ | ❌ |

## Rationale

- Honest help output — flags only appear where they do something
- No silent ignores — `csg --runtime container version` becomes an error
- No wasted processor construction — build only when needed
- No leakage of overrides into commands that don't need them
- Config file and ENV override paths still work unchanged
- `None` defaults allow TOML/ENV to be the baseline
- Shared factories eliminate duplication and enable consistent help text
- WEG `cli_overrides` plumbing uses the existing config-assembler mechanism instead of post-resolution mutation

## Implementation

See `openspec/changes/cli-flag-scope-refinement/` for the complete change artifacts (spec delta, design, tasks).
