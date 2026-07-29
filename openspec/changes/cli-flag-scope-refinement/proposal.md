## Why

21 of 23 CLI commands across CSG and WEG silently accept `--runtime` and/or `--container-engine` from the global `@app.callback()` even though they don't consume them. This creates misleading help output (flags listed on `--help` for commands that ignore them), wasteful eager processor construction in CSG, and an inconsistent architecture between the two tools. The user cannot tell from a command's own `--help` whether a flag affects behavior.

## What Changes

Scopes every CLI flag to exactly the command tree that consumes it, following the principle: a flag's declaration scope must match its set of actual consumers.

**Specific changes:**

1. **Remove `--runtime` and `--container-engine` from root `@app.callback()` in both tools.** These two flags account for 100% of the silent-ignore instances.
2. **Scope `--runtime`** to the commands that build/use a processor:
   - CSG: `generate` only (leaf option)
   - WEG: `process` sub-typer callback + `batch` sub-typer callback
3. **Scope `--container-engine`** to the commands that directly consume it:
   - CSG: `generate`, `install`, `uninstall` (leaf options)
   - WEG: `process` sub-typer callback, `batch` sub-typer callback, `install`, `uninstall` (leaf options)
4. **Centralize option definitions** in a shared `cli/options.py` module so leaf commands import `runtime_opt`/`engine_opt` constants rather than re-declaring options inline.
5. **Drop redundant `-e`/`-c`/`-p` override options** on WEG `process effect|composite|preset` — the positional argument already carries the name, the extra option is pure duplication.
6. **Make CSG processor construction lazy:** move processor building from the eager root callback into the `generate` command body (modeled on WEG's existing `_resolve_processor()` pattern).
7. **Wire `cli_overrides` through WEG's `AssembledConfigResolver.resolve()`** so the config-assembler-engine's CLI override mechanism is actually used, matching CSG's existing plumbing.

**Non-goals:** config/ENV resolution, domain models, ports, adapters, output formatting, verbosity handling — none of these change. Root callback retains `--config`, `--templates-dir`/`--effects`, `--output-format`, `--verbose`/`--quiet` as cross-cutting resolution/output concerns.

## Capabilities

### New Capabilities
- `cli-flag-factories`: Shared `typer.Option` definitions for `--runtime` and `--container-engine` in `cli/options.py` — single source of truth, imported by leaf commands that need them.
- `cli-lazy-processor-csg`: CSG builds the processor lazily in the `generate` command body instead of eagerly in the root callback, matching WEG's pattern.

### Modified Capabilities
- `cli-runtime-engine-scope`: Update the existing spec to reflect the refined scoping — previously stated both flags go to per-command but was vague on scope boundaries; now precisely defined per the full consumer table.

## Impact

- **CLI surface**: `csg --help` and `weg --help` output changes — `--runtime` and `--container-engine` no longer appear in the global options section. Each command shows only its own flags in `--help`.
- **CLI adapter code (8 files)**: CSG `main.py`, WEG `main.py`, WEG `process.py`, WEG `batch.py`, CSG `install_cmd.py`, CSG `uninstall_cmd.py`, WEG `install.py`, WEG `uninstall.py` — option declarations added/removed, processor construction moved.
- **New file**: `cli/options.py` in both tools (or one shared per tool).
- **Config resolution (1 file)**: WEG `assembled_config_resolver.py` gains `cli_overrides` parameter plumbed through.
- **Tests (5 files)**: Flag placement assertions must update per new positions.
- **No changes**: Domain, ports, adapters other than the above, factory (beyond lazy build), models, enums.
