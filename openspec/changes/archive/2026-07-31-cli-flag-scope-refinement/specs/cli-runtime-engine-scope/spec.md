## MODIFIED Requirements

### Requirement: CLI flag scoping for --runtime and --container-engine

`--runtime` and `--container-engine` SHALL be scoped to exactly the commands that consume them. The root `@app.callback()` SHALL NOT declare either flag.

- `--runtime` SHALL be available only on commands that build and use a processor: CSG `generate`, WEG `process` sub-typer, WEG `batch` sub-typer.
- `--container-engine` SHALL be available on commands that directly consume it: CSG `generate`, CSG `install`, CSG `uninstall`, WEG `process` sub-typer, WEG `batch` sub-typer, WEG `install`, WEG `uninstall`.
- All other commands SHALL NOT accept either flag. Passing `--runtime` or `--container-engine` to a non-consuming command SHALL produce a typer parse error.

Both flags SHALL default to `None` (optional). When omitted, the command SHALL fall back to the resolved TOML/ENV config value.

**Previous:** `--runtime` and `--container-engine` were defined in the root `@app.callback()` of both tools, making them globally available to all commands regardless of whether they consumed them.

#### Scenario: generate accepts --runtime and --container-engine

- **WHEN** `csg generate img.png --runtime container --container-engine podman` is run
- **THEN** `generate` uses the container runtime with Podman engine to produce the palette

#### Scenario: info rejects --runtime

- **WHEN** `csg info --runtime container` is run
- **THEN** typer returns a parse error: `Error: no such option: --runtime`

#### Scenario: info rejects --container-engine

- **WHEN** `csg info --container-engine podman` is run
- **THEN** typer returns a parse error: `Error: no such option: --container-engine`

#### Scenario: version rejects both flags

- **WHEN** `csg --runtime container version` is run (flag before command name)
- **THEN** typer returns a parse error: `Error: no such option: --runtime`

#### Scenario: process accepts both flags (WEG)

- **WHEN** `weg process --runtime container --container-engine podman effect blur img.png` is run
- **THEN** `process effect` uses the container runtime with Podman engine

#### Scenario: batch accepts both flags (WEG)

- **WHEN** `weg batch --runtime container --container-engine podman effects ./walls` is run
- **THEN** `batch effects` uses the container runtime with Podman engine

#### Scenario: install accepts --container-engine only

- **WHEN** `csg install --container-engine podman` is run
- **THEN** `install` builds the container image using Podman

#### Scenario: install rejects --runtime

- **WHEN** `csg install --runtime container` is run
- **THEN** typer returns a parse error: `Error: no such option: --runtime`

#### Scenario: show effects rejects both flags (WEG)

- **WHEN** `weg show effects --runtime container` is run
- **THEN** typer returns a parse error: `Error: no such option: --runtime`

### Requirement: Option definitions centralized in cli/options.py

**ADDED.** Each tool SHALL provide `cli/options.py` exporting `RUNTIME_OPT` and `ENGINE_OPT` as shared `typer.Option` instances. No inline option re-declaration SHALL occur across multiple leaf commands.

#### Scenario: Shared option is used by generate and install (CSG)

- **WHEN** `csg generate` and `csg install` both import `ENGINE_OPT` from `cli/options.py`
- **THEN** both commands parse `--container-engine` independently from the same `typer.Option` definition

### Requirement: Explicit final command shapes

**MODIFIED.** The previous spec listed `csg show` as having both flags — this was incorrect. `show` SHALL NOT carry either flag.

**Correct CSG shape:**

| Command | `--runtime` | `--container-engine` |
|---|---|---|
| `csg generate` | ✅ | ✅ |
| `csg info` | ❌ | ❌ |
| `csg show` | ❌ | ❌ |
| `csg install` | ❌ | ✅ |
| `csg uninstall` | ❌ | ✅ |
| `csg dump-config` | ❌ | ❌ |
| `csg dump-templates` | ❌ | ❌ |
| `csg list-backends` | ❌ | ❌ |
| `csg version` | ❌ | ❌ |

**Correct WEG shape:**

| Command | `--runtime` | `--container-engine` |
|---|---|---|
| `weg process` (sub-typer) | ✅ | ✅ |
| `weg batch` (sub-typer) | ✅ | ✅ |
| `weg install` | ❌ | ✅ |
| `weg uninstall` | ❌ | ✅ |
| `weg info` | ❌ | ❌ |
| `weg version` | ❌ | ❌ |
| `weg show *` | ❌ | ❌ |
| `weg dump-config` | ❌ | ❌ |
| `weg dump-effects` | ❌ | ❌ |

#### Scenario: csg show carries neither flag

- **WHEN** `csg show --runtime container img.png` is run
- **THEN** typer returns a parse error: `Error: no such option: --runtime`
- **AND** `csg show --container-engine podman img.png` also returns a parse error

#### Scenario: install carries --container-engine only

- **WHEN** `csg install --container-engine podman` is run
- **THEN** the command succeeds
- **AND** `csg install --runtime container` returns a parse error for `--runtime`

#### Scenario: weg show leaves carry neither flag

- **WHEN** `weg show effects --runtime container` is run
- **THEN** typer returns a parse error: `Error: no such option: --runtime`
- **AND** `weg show effects --container-engine podman` also returns a parse error

## REMOVED Requirements

### Requirement: Per-command flag on CSG show

**Reason:** The investigation confirmed `csg show` consumes processor indirectly via the root callback but doesn't need explicit runtime/engine flags. It builds its processor from TOML/ENV config, which is an implementation detail the user should not need to think about for a display-only command.

**Migration:** `csg show` no longer accepts `--runtime` or `--container-engine`. Any scripts passing these flags to `show` must remove them.

### Requirement: Redundant -e/-c/-p override options on WEG process

**Reason:** The positional `name` argument already carries the effect/composite/preset name. The `-e`/`--effect`, `-c`/`--composite`, `-p`/`--preset` override options were pure aliases with no behavioral value.

**Migration:** Remove `effect_name`, `composite_name`, `preset_name` parameters and their corresponding `-e`/`-c`/`-p` options from `process effect`, `process composite`, `process preset`. The positional argument is sufficient.
