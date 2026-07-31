## Why

Both WEG and CSG have a container processor adapter that constructs a CLI
argv passed into the container for execution — `weg process effect …` and
`csg generate …` respectively. This argv is currently built using CLI
flags (`--config`, `--effects`, `--runtime`) that are positioned at a
specific flag scope (root, sub-typer callback, or leaf).

This creates a **hidden coupling**: any change to the CLI's flag-scoping
layout silently breaks the adapter. The coupling exists because:

1. The adapter and the CLI share no code — the adapter manually positions
   flags without importing option definitions or using the CLI parser.
2. Existing unit tests assert on `result.command` with loose substring
   checks (e.g. `"process effect blur" in result.command`) that pass
   even when flag positioning is wrong.
3. The mock-engine test pattern simulates container success without ever
   validating the argv against the actual CLI parser.

This was not theoretical: `cli-flag-scope-completion` (commit `29883d2`)
moved `--config`/`--effects` from root to sub-typer callbacks but never
updated `_build_weg_command()`. The result — `weg batch all` fails 9/9
with `"No such option: --config"`.

Additionally, CSG's `container_processor.py` has a **pre-existing latent
bug** of the same class: it positions `--runtime local` at root level
(`["csg", "--runtime", "local", "generate", …]`), but `--runtime` is a
leaf option on the `generate` command (it was moved there before `cli-flag-scope-completion`).
This has never surfaced because the pre-flag-scope container image may
still accept the old root-level form, but it will break on the next
`weg install` rebuild.

## What Changes

### 1. WEG container adapter — migrate to env vars

Replace `--config` and `--effects` CLI flags in the in-container argv
with environment variables in `RunConfig.environment`, matching CSG's
existing `_CONTAINER_ENV` pattern:

```
env: {
    HOME:                "/tmp"
    XDG_CONFIG_HOME:     "/tmp/.config"
    XDG_CACHE_HOME:      "/tmp/.cache"
    WALLPAPER_CONFIG_FILE_PATH:     "/weg-config/settings.toml"
    WALLPAPER_EFFECTS_CONFIG_FILE_PATH: "/weg-effects/effects.yaml"
    WALLPAPER__RUNTIME__MODE:       "local"
}
```

The argv changes from:
```
weg --config X --effects Y process effect NAME INPUT -o OUTPUT --param k=v
```
to:
```
weg process effect NAME INPUT -o OUTPUT --param k=v
```
(No `--config`/`--effects`/`--runtime` flags at all — env vars handle them.)

### 2. CSG container adapter — fix `--runtime` scope

Move `--runtime local` from the CLI argv into the environment as
`COLORSCHEME__RUNTIME__MODE=local`, same `_CONTAINER_ENV` pattern.

The argv changes from:
```
csg --runtime local generate /input/NAME --backend b --param k=v -o /output
```
to:
```
csg generate /input/NAME --backend b --param k=v -o /output
```

### 3. Add interface contract tests (both tools)

For each tool, add a test that constructs the adapter's argv via the
production `_build_weg_command`/`process_generate` path, then parses it
through the live `typer.testing.CliRunner` against the real CLI `app`.

This catches any future flag-scope mismatch between adapter and CLI
at the earliest possible point — during `pytest`, not `weg batch all`.

### 4. Add env-contract tests (both tools)

Assert that the `RunConfig.environment` dict passed into the container
includes a complete set of env vars covering file paths (config + effects)
and runtime overrides. Pattern: CSG's existing `test_passes_expected_environment`.

### 5. Remove dead code (`output_name` in WEG)

Line 153 of `container_processor.py` computes `output_name` but never
uses it. Remove.

## Capabilities

### New Capabilities

- `container-adapter-env-contract`: Defines the canonical set of
  environment variables that WEG and CSG container processors must pass
  into their containers for resource discovery. Replaces CLI-flag-based
  discovery, decoupling the adapter from flag-scope decisions.

- `interface-contract-test`: Validation pattern where an adapter's
  constructed argv is run through the live CLI parser to detect any
  drift between what the adapter builds and what the CLI accepts.

### Modified Capabilities

- `container_processor.py` (WEG + CSG): The in-container argv is
  simplified — only positional arguments, per-leaf options (`-o`,
  `--backend`, `--param`), and `--param` overrides remain. Config/resource
  paths and runtime decisions are passed via env vars.

## Impact

### Files changed

#### WEG (4 files)

| File | Change |
|------|--------|
| `adapters/container_processor.py` | Add `_CONTAINER_ENV` dict; pass via `RunConfig.environment`; remove `--config`/`--effects` from `_build_weg_command`; remove dead `output_name` |
| `tests/unit/adapters/test_container_processor.py` | Add interface contract test; update assertions to exact argv shape; add env-contract test |
| `tests/unit/cli/test_process_commands.py` | Update flag-position assertions in process tests |
| `tests/test_cli.py` | Update flag-position assertions |

#### CSG (3 files)

| File | Change |
|------|--------|
| `adapters/container_processor.py` | Add `COLORSCHEME__RUNTIME__MODE=local` to `_CONTAINER_ENV`; remove `--runtime local` from both `inner_command` in `process_generate` and `process_show` |
| `tests/unit/adapters/test_container_processor.py` | Add interface contract test; update `test_inner_command_contains_runtime_local` and `test_show_inner_command_has_runtime_local` to reflect removed flags; update env-contract test |
| `tests/unit/cli/test_cli.py` | Update flag-position assertions if any |

### Test suite

- 480+ tests pass (both tools).
- New tests fail if adapter argv drifts from CLI parser expectations.
