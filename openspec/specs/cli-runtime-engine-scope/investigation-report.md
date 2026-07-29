# Investigation: CLI Runtime & Engine Flag Scope — Full Report

## 1. Verified Command-by-Command Matrix

### CSG (`color-scheme-generator`)

Source: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/`

| Command | File | Uses `--runtime`? | Uses `--container-engine`? | How |
|---|---|---|---|---|
| **generate** | `main.py` (inline `app.command`) | **Indirect** — callback built `deps.processor` from `--runtime` before command runs | **Via `cli_overrides`** — `ctx.obj["cli_overrides"]` contains `"container.engine"`, passed to `config_resolver.resolve()` |
| **show** | `show.py` | **Indirect** — same as `generate`, uses `deps.processor` | **Via `cli_overrides`** — same as `generate` |
| **install** | `install_cmd.py` | **No** | **Yes, direct** — `ctx.obj.get("container_engine")` raw enum, bypasses `cli_overrides` |
| **uninstall** | `uninstall_cmd.py` | **No** | **Yes, direct** — same pattern as `install` |
| **info** | `info_cmd.py` | **No** | **Only via `cli_overrides`** — `ctx.obj["cli_overrides"]` passed to `config_resolver.resolve()`, but `--runtime` was never added to overrides |
| **dump-config** | `dump_config_cmd.py` | **No** | **Only via `cli_overrides`** — same as `info` |
| **dump-templates** | `dump_templates_cmd.py` | **No** | **No** |
| **list-backends** | `list_backends_cmd.py` | **No** | **No** |
| **version** | `version_cmd.py` | **No** | **No** |

**Preliminary analysis verdict: ACCURATE.** The only nuance is that `info` and `dump-config`'s use of `--container-engine` is purely cosmetic (it flows into the resolved settings object but doesn't change behavior for these read-only commands).

### WEG (`wallpaper-effects-generator`)

Source: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/`

| Command | File | Uses `--runtime`? | Uses `--container-engine`? | How |
|---|---|---|---|---|
| **process effect** | `process.py` | **Yes** — `_resolve_context()` reads `ctx.obj["runtime"]` | **Yes** — `_resolve_context()` reads `ctx.obj["container_engine"]` |
| **process composite** | `process.py` | **Yes** — same path | **Yes** — same path |
| **process preset** | `process.py` | **Yes** — same path | **Yes** — same path |
| **batch effects** | `batch.py` | **Yes** — via `_run_batch()` → `_resolve_context()` | **Yes** — same path |
| **batch composites** | `batch.py` | **Yes** — same path | **Yes** — same path |
| **batch presets** | `batch.py` | **Yes** — same path | **Yes** — same path |
| **batch all** | `batch.py` | **Yes** — same path | **Yes** — same path |
| **install** | `install.py` (main.py inline) | **No** | **Yes, direct** — `ctx.obj.get("container_engine")` passed to `install_command()` |
| **uninstall** | `uninstall.py` (main.py inline) | **No** | **Yes, direct** — same pattern |
| **info** | `info.py` (main.py inline) | **No** | **No** |
| **show effects** | `show.py` | **No** | **No** |
| **show composites** | `show.py` | **No** | **No** |
| **show presets** | `show.py` | **No** | **No** |
| **show all** | `show.py` | **No** | **No** |
| **dump-config** | `dump_config.py` (main.py inline) | **No** | **No** |
| **dump-effects** | `dump_effects.py` (main.py inline) | **No** | **No** |
| **version** | `version_cmd.py` (main.py inline) | **No** | **No** |

**Preliminary analysis verdict: ACCURATE.** All claims confirmed.

---

## 2. `--help` Output Audit

### CSG

| Command | `--runtime` visible? | `--container-engine` visible? | Misleading? |
|---|---|---|---|
| `csg --help` | Yes (global options) | Yes (global options) | Baseline — expected |
| `csg generate --help` | **No** | **No** | Not misleading — Typer hides global options from subcommand help |
| `csg info --help` | **No** | **No** | Not misleading — but unexpected; user might not know the flag exists |
| `csg version --help` | **No** | **No** | Not misleading |
| `csg install --help` | **No** | **No** | Not misleading — but user can't discover `--container-engine` here |
| `csg show --help` | **No** | **No** | Not misleading |

### WEG

| Command | `--runtime` visible? | `--container-engine` visible? | Misleading? |
|---|---|---|---|
| `weg --help` | Yes (global options) | Yes (global options) | Baseline |
| `weg process effect --help` | **No** | **No** | Not misleading — but user can't discover these flags from subcommand help |
| `weg install --help` | **No** | **No** | Not misleading — but user can't discover `--container-engine` here |
| `weg info --help` | **No** | **No** | Not misleading |

### Key finding

Typer inherits global options to all subcommands by default, but they do **not appear in subcommand `--help` output**. The user only sees them on the top-level `--help`. This means:

- **No command actually shows misleading flags in its own `--help`** — the spec's concern about "misleading help" is about the flags being *accepted* silently, not about them being *displayed*.
- **Discoverability is poor**: a user typing `csg install --help` won't see `--container-engine` listed, but `csg install --container-engine podman` works. User needs to know the global flags exist from `csg --help`.

---

## 3. Config/ENV Interaction Analysis

### Override engine priority (config-assembler-engine)

The shared library at `src/shared/config-assembler-engine/` defines a strict priority:

1. **TOML config file** values (baseline)
2. **ENV var overrides** (applied second — `COLORSCHEME__RUNTIME__MODE`, `WALLPAPER__*__*`)
3. **CLI flag overrides** (applied last — always wins)

This is enforced via `sorted_overrides = sorted(overrides, key=lambda o: 0 if o.source == OverrideSource.ENV else 1)` in `use_cases.py`.

### CSG: how flags interact with config

| Setting | TOML/ENV honored? | CLI mechanism | Notes |
|---|---|---|---|
| `runtime.mode` | **No** — TOML value determines `settings.runtime.mode` but NOT processor type | `--runtime` consumed in callback to build processor | **Critical design issue**: `--runtime container` is the only way to enable container mode. TOML `runtime.mode = "container"` and `COLORSCHEME__RUNTIME__MODE=container` have NO effect on processor selection. |
| `container.engine` | **No** — TOML value always overridden by CLI default | `--container-engine` has non-None default (`docker`), so `cli_overrides["container.engine"]` is always the default value | **Critical design issue**: Setting `container.engine = "podman"` in TOML is silently ignored because `if container_engine is not None` is always True (CLI default is `docker`). |

### WEG: how flags interact with config

| Setting | TOML/ENV honored? | CLI mechanism | Notes |
|---|---|---|---|
| `runtime.mode` | **Yes** — TOML/ENV is baseline, CLI is optional override | `--runtime` has `None` default, post-resolution mutation in `_resolve_context()` | Clean design: if user omits flag, TOML/ENV controls. |
| `container.engine` | **Yes** — TOML/ENV is baseline, CLI is optional override | `--container-engine` has `None` default, post-resolution mutation in `_resolve_context()` | Clean design: same pattern. |

### CSG anomaly: redundant `cli_overrides`

CSG adds `container.engine` to `cli_overrides` in the callback (line 160 of `main.py`). But the **actual engine used** comes from the direct `create_container_engine(engine=container_engine)` call (line 165), not from the override system. The overridden value in `settings.container.engine` is read by no downstream consumer for actual engine selection — it only populates the settings struct for informational/config-dump purposes.

### WEG anomaly: `cli_overrides` parameter exists but never used

WEG's `assembled_config_resolver.py` `resolve()` method signature accepts `explicit_path` but **not** `cli_overrides`. The override rules declare `OverrideSource.CLI` as accepted, but there's no path to inject CLI values. Only ENV vars and TOML values actually flow through the override system. CLI flags are applied post-resolution via object mutation in `_resolve_context()`.

---

## 4. Test Audit

### Tests that would break if flags moved to per-command

| Test file | Tool | Lines | What it tests | Why it would break |
|---|---|---|---|---|
| `tests/unit/cli/test_runtime_mode.py` | CSG | 85–130 | `TestRuntimeFlags` passes `--runtime`/`--container-engine` to `version` command | Flags given globally before subcommand; `version` doesn't need them |
| `tests/unit/cli/test_process_commands.py` | WEG | 187–290 | `TestContainerEngineFlag` passes `--container-engine`/`--runtime` before `process effect` | Flags given globally; would need to be positioned differently |
| `tests/test_cli.py` | WEG | 128–129 | `test_info_command` passes `--runtime container` to `info` | Info ignores `--runtime`; flag would need removal |
| `tests/unit/cli/test_install_command.py` | CSG | 130 | `test_install_engine_podman` passes `--container-engine podman` globally to `install` | Would need flag repositioning |
| `tests/test_user_journey.sh` | CSG | 161, 194 | Expects `--runtime` in help text; passes `--runtime local info` | Help text changes; flag on `info` needs removal |

### Tests that would NOT break (but are related)

| Test file | Tool | Relevance |
|---|---|---|
| `tests/unit/adapters/test_container_processor.py` | CSG | Verifies inner container command includes `--runtime local` — adapter internals, unrelated to CLI flag scope |
| `tests/test_enums.py` | WEG | Tests `RuntimeMode`/`ContainerEngine` enum values — domain logic |
| `tests/test_models.py` | WEG | Tests `AppSettings`/`RuntimeSettings` construction — domain logic |
| `tests/unit/domain/test_models.py` | CSG | Same — domain logic |
| `tests/unit/adapters/settings/test_config_resolver.py` | CSG | Tests config resolution with TOML/ENV — unaffected by CLI flag scope |
| `tests/test_assembled_config_resolver.py` | WEG | Same |
| `tests/unit/adapters/settings/test_settings_serializer.py` | CSG | Serialization tests — domain logic |
| `tests/unit/adapters/serializer/test_settings_serializer.py` | WEG | Same |
| `tests/test_factory.py` | WEG | Factory construction — domain logic |
| `tests/unit/cli/test_info_command.py` | CSG | References `RuntimeMode` for mock setup — not CLI-flag-specific |
| `tests/unit/cli/test_dump_config_command.py` | CSG | Same |
| `tests/unit/cli/test_uninstall_command.py` | CSG | References `ContainerEngine` for constructing test data — not CLI-flag-specific |
| `tests/unit/adapters/test_dry_run_processor.py` | CSG | References runtime mode for processor selection — domain logic |

### Summary

**5 test files** would need changes. **13 other test files** reference these types but are unaffected.

---

## 5. Architecture Divergence

### CSG pattern: eager consumption

```
main_callback()
  ├── reads --runtime immediately
  ├── creates deps.processor (LocalProcessor or ContainerProcessor)
  ├── stores processor in ctx.obj["deps"]
  └── NEVER stores --runtime itself
```

- Processor is wired up before any command runs
- Commands (`generate`, `show`) use `deps.processor` — they don't know or care about `--runtime`
- `--container-engine` is dual-path: stored in `cli_overrides` for config AND used directly for engine creation
- `install`/`uninstall` bypass everything and read `ctx.obj["container_engine"]` directly

### WEG pattern: lazy resolution

```
main_callback()
  ├── reads --runtime, stores raw value in ctx.obj["runtime"]
  ├── reads --container-engine, stores raw value in ctx.obj["container_engine"]
  └── creates bare CliDependencies (no processor)
```

- Each processing command's `_resolve_context()` resolves config, then applies CLI overrides post-resolution
- `_resolve_processor()` branches on `settings.runtime.mode` to create the right processor
- `install`/`uninstall` receive `container_engine` as an explicit parameter from `ctx.obj.get()`

### Does the divergence matter?

**Yes, for three reasons:**

1. **CSG's eager pattern creates unreachable code paths.** When `--runtime container` is passed, the callback creates a `ContainerProcessor`. But if the user runs `csg info`, the processor is built and immediately discarded — `info` never calls `deps.processor.process_*()`.

2. **CSG cannot honor TOML/ENV runtime settings.** The eager callback unconditionally creates a processor based on the CLI flag, ignoring what TOML says. WEG's lazy pattern lets TOML/ENV control the default, with CLI as override.

3. **WEG's `_resolve_context()` is called independently by each command**, meaning it re-resolves config on every invocation. CSG resolves config at most once (lazily cached in pre-command setup — though both tools' config resolvers don't cache, so WEG re-resolves each time).

### Should they converge?

Converging to the WEG lazy pattern would be more flexible (TOML/ENV honored as baseline, CLI as override). However, CSG's eager pattern is simpler for readers — the processor is a dependency set up once. The tradeoff is the silent override of TOML settings.

---

## 6. Install/Uninstall Asymmetry

### CSG: `install`/`uninstall` bypass the normal flag path

```python
# install_cmd.py line 48-49
settings = deps.config_resolver.resolve()  # No cli_overrides passed!
engine = ctx.obj.get("container_engine") or ContainerEngine(settings.container.engine) or ContainerEngine.DOCKER
```

**Two inconsistencies:**

1. **No `cli_overrides` passed**: unlike `generate`/`show` which pass `cli_overrides = ctx.obj.get("cli_overrides", {})` to `config_resolver.resolve()`, `install`/`uninstall` call `resolve()` with no args. This means `--verbose`/`--quiet` and `--templates-dir` overrides (which ARE in `cli_overrides`) are also skipped for `install`/`uninstall`.

2. **Direct `ctx.obj` read as fallback chain**: `ctx.obj.get("container_engine")` → `settings.container.engine` → `ContainerEngine.DOCKER`. This creates a fallback: CLI flag wins, then TOML, then hardcoded default. But `ctx.obj["container_engine"]` is ALWAYS set to the CLI default (`DOCKER`) because of the non-None default, so the TOML value is never reached in practice.

### WEG: `install`/`uninstall` receive `container_engine` as a parameter

```python
# main.py line 212
install_command(
    container_engine=ctx.obj.get("container_engine"),
    ...
)
```

Then in the command itself (install.py):
```python
if container_engine is not None:
    container = ContainerSettings(engine=container_engine.value, ...)
```

**WEG's pattern is cleaner**: CLI flag is optional (`None`-defaulted), so TOML/ENV is respected when flag is omitted. No fallback chain, no config resolver bypass for the `install` path.

### Does the CSG inconsistency matter?

**Yes.** The key practical issue: if a user sets `container.engine = "podman"` in their `settings.toml` and runs `csg install` (without `--container-engine` flag), the TOML setting is **silently ignored** because:
1. `--container-engine` has a non-None default (`docker`)
2. The fallback chain never reaches `settings.container.engine`
3. The docker default wins

This is a bug in CSG, not just an inconsistency.

---

## 7. Options Space (A–E)

### A. Per-command flags

Remove `--runtime` and `--container-engine` from `@app.callback()` and add them as parameters to each command that needs them.

**CSG commands gaining flags:**
- `generate` — needs both
- `show` — needs both
- `install` — needs `--container-engine` only
- `uninstall` — needs `--container-engine` only
- `info` — neither needed (remove `cli_overrides` pass-through too?)
- `dump-config` — neither needed (same question)
- `dump-templates`, `list-backends`, `version` — neither

Total: 4 commands gain flags (2 get both, 2 get one). The rest lose the global.

**WEG commands gaining flags:**
- `process_app` sub-typer: `effect`, `composite`, `preset` — needs both (3 commands)
- `batch_app` sub-typer: `effects`, `composites`, `presets`, `all` — needs both (4 commands)
- `install` — needs `--container-engine`
- `uninstall` — needs `--container-engine`
- `info`, `show_app` (4), `dump-config`, `dump-effects`, `version` — neither

Total: 9 commands gain flags (7 get both, 2 get one). Plus duplication across the sub-typers.

**Duplication cost:** The option definitions (type, help text, default, validation) must be repeated for each command. Typer supports this but it violates DRY. Could mitigate with a shared `RUNTIME_OPTION`/`CONTAINER_ENGINE_OPTION` constant imported by each module.

**Typer support:** Typer allows `typer.Option(...)` on any command function, including sub-typer commands. No issues.

### B. Sub-typer grouping

Move flags from root callback to sub-typer callbacks in WEG where sub-typers already exist.

**WEG changes:**
- `process_app.callback()` gets `--runtime` and `--container-engine` — scoped to all `process *` commands
- `batch_app.callback()` gets `--runtime` and `--container-engine` — scoped to all `batch *` commands
- Root `install` and `uninstall` still need access — either add `--container-engine` to root callback (but not `--runtime`) or add it per-command
- `show_app`, `info`, `dump-*`, `version` remain flag-free

**CSG changes:** CSG doesn't have sub-typers, so no natural grouping exists. Would need to either:
- Create a `process_app` sub-typer and move `generate`/`show` under it (breaking change: `csg generate` → `csg process generate`)
- Or leave as-is and handle `install`/`uninstall` separately

**Install/uninstall with B:** They'd need `--container-engine` on a separate scope. Options:
- Keep `--container-engine` on root (hybrid approach — see option E)
- Add it per-command for `install`/`uninstall` only

### C. Keep global but add warnings

Detect when a flag is passed but the command doesn't use it, emit a warning.

**Implementation complexity:**
- Could add a wrapper decorator that checks `ctx.obj` for flags the command doesn't read
- Or add a `@uses_runtime`/`@uses_container_engine` decorator to commands, and warn if a flag is set without the decorator
- Typer's callback runs before the command; you'd need a way to know the target command at callback time

**Value:** Low. The warning would fire every time a user passes the flag correctly on a command that uses it (false positive risk). Hard to distinguish "user explicitly passed it" from "default value was set".

**Runtime concerns:** In CSG, `--runtime` has a non-None default, so it's impossible to tell if the user explicitly passed `--runtime local` or if it's the default. Every command would get a warning.

### D. Remove from CLI, keep in config only

Remove `--runtime` and `--container-engine` as CLI flags. Users set them via TOML or ENV vars.

**Impact:**
- `csg --runtime container generate` → users must run `COLORSCHEME__RUNTIME__MODE=container csg generate` or edit settings.toml
- `csg --container-engine podman generate` → `COLORSCHEME__CONTAINER__ENGINE=podman csg generate`
- Weg: same pattern with `WALLPAPER_*` prefix

**Current feasibility — CSG:** Actually **not feasible without code changes**. CSG's callback reads `--runtime` to build the processor and ignores `runtime.mode` from config. Even if you set `COLORSCHEME__RUNTIME__MODE=container`, the callback defaults to `--runtime local` and creates a `LocalProcessor`. The code must change to respect TOML/ENV runtime settings.

**Current feasibility — WEG:** **Feasible.** WEG already respects TOML/ENV as baseline with CLI as optional override. Removing CLI flags would leave TOML/ENV as the only path — which already works.

**User impact:** Power users who frequently switch runtimes would need to set ENV vars or edit config files. CI/CD pipelines would need ENV var configuration.

### E. Split the pair

Move only `--runtime` to per-command while `--container-engine` stays global, or vice versa.

**Commands needing `--runtime` (not `--container-engine`):** None. Every command that uses `--runtime` also uses `--container-engine`. The reverse is not true: `install`/`uninstall` need `--container-engine` but not `--runtime`.

**Commands needing `--container-engine` (not `--runtime`):** `install`, `uninstall` in both tools.

**Viable split:** Move `--runtime` to per-command (for `generate`, `show`, `process`, `batch`), keep `--container-engine` global (used by processing commands + `install` + `uninstall`). This reduces the misleading-flag surface by half but leaves `--container-engine` on `info`/`version` etc.

**Alternative split:** Move `--container-engine` to per-command, keep `--runtime` global. But `--runtime` is the more confusing one (it suggests execution isolation but is silently ignored on most commands). Keeping it global doesn't help.

**Best split candidate:** `--runtime` → per-command (or sub-typer), `--container-engine` → remain global. Rationale: `--container-engine` is needed by more commands (including `install`/`uninstall`), and its meaning ("which container tool") is less surprising when accepted by a non-processing command. `--runtime` is more misleading ("will this run inside a container?") and should only appear where it matters.

---

## 8. External Precedent

| Tool | Pattern | Notes |
|---|---|---|
| **docker** | Per-command options | `docker run --rm` is meaningless on `docker ps`. Flags scoped to commands that need them. `docker --config` is global (config path). |
| **git** | Per-command options | `git commit --amend` would error on `git log`. Some global options (`--git-dir`, `--work-tree`). `git -c key=value` is the universal override mechanism. |
| **kubectl** | Per-command options + global config | `kubectl run --image` would error on `kubectl get`. `--kubeconfig` and `--context` are global. `kubectl --namespace` is global but `kubectl get pods --namespace` also works (namespace is relevant everywhere). |
| **aws CLI** | Per-command + global profile/region | `--region` is global (needed by all commands). `--cli-input-json` is global (format option). |
| **gh (GitHub CLI)** | Per-command + global auth/host | `--repo` is global (needed by repo commands). `gh pr create --title` would error on `gh issue list`. |
| **uv** | Per-command + global project flags | `--python` is global (used everywhere). `uv add --dev` is scoped to add. |

**Key insight:** The industry norm is to scope flags to the commands that need them. Global flags are reserved for things that truly apply to all subcommands (config paths, auth tokens, output formatting). Runtime/execution mode is typically a per-command concern.

---

## Additional Dimensions Discovered

### CSG default-override bug

CSG's `--runtime` and `--container-engine` have non-None Typer defaults (`RuntimeMode.LOCAL`, `ContainerEngine.DOCKER`). Combined with `if X is not None` checks in the callback, this means:
- The user **cannot** express "use whatever the TOML/ENV says" via CLI omission — omission is interpreted as the default value
- This is a design smell: defaults should be `None` (optional) if TOML/ENV is meant to have authority

### CSG `cli_overrides` contains `container.engine` even when `--runtime local`

The callback adds `cli_overrides["container.engine"]` unconditionally (line 160), even when running locally. This means `container.engine` is injected into the config resolution pipeline even for local operations where no container engine is used. Harmless but untidy.

### `info` and `dump-config` have a phantom dependency on `--container-engine`

These commands fetch `cli_overrides` from `ctx.obj` and pass it to `config_resolver.resolve()`. Since `cli_overrides` always contains `container.engine` (due to the non-None default), the engine appears in resolved settings even for these read-only commands. If a user runs `csg --container-engine podman dump-config`, they see `container.engine = "podman"` in the output — which is technically correct (CLI flag set it) but misleading (no container operation will be performed).

### WEG's `show` sub-typer could be a model for CSG

WEG already groups commands by function: `process`, `show`, `batch`. If CSG adopted sub-typers, `generate` and `show` could live under a `process_app` sub-typer that carries `--runtime` and `--container-engine`. But this breaks the current `csg generate` / `csg show` UX — users would type `csg process generate` / `csg process show`.
