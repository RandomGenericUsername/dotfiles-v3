# CLI Runtime & Engine Scope — Investigate and Design

## 1. Verified Current State

### CSG (`color-scheme-generator`)

**App:** `cli/main.py:53` — `app = typer.Typer(name="csg")`

**Callback:** `cli/main.py:88` — `@app.callback()` defines both `--runtime` (default LOCAL) and `--container-engine` (default DOCKER) as global options.

| Command | Defined in | Consumes `--runtime`? | Consumes `--container-engine`? | Lines |
|---|---|---|---|---|
| `generate` | `cli/main.py:194` | Via callback (processor built) | No (processor already built) | 162-169, 264 |
| `show` | `cli/show.py:21` | Via callback (processor built) | No | 61 |
| `info` | `cli/info_cmd.py:27` | **No** (ignored) | Via `cli_overrides` only | 40-43 |
| `dump-config` | `cli/dump_config_cmd.py:13` | **No** | Via `cli_overrides` only | 26-27 |
| `dump-templates` | `cli/dump_templates_cmd.py:19` | **No** | **No** | — |
| `install` | `cli/install_cmd.py:41` | **No** | **Yes** (direct read) | 49 |
| `uninstall` | `cli/uninstall_cmd.py:19` | **No** | **Yes** (direct read) | 29 |
| `list-backends` | `cli/list_backends_cmd.py:52` | **No** | **No** | — |
| `version` | `cli/version_cmd.py:15` | **No** | **No** | — |

**How `--runtime` flows:**
- Callback consumes it at `main.py:162-169` to decide which processor to build
- `--runtime` is **not** added to `cli_overrides` (see `main.py:154-160`)
- Commands that don't need a processor (version, dump-templates, etc.) trigger wasteful eager construction

**How `--container-engine` flows:**
- Stored in `ctx.obj["container_engine"]` at `main.py:174`
- Also pushed to `cli_overrides["container.engine"]` at `main.py:159-160` → feeds into config-assembler-engine
- `install`/`uninstall` read it directly from `ctx.obj` to create a container engine
- Other commands ignore the direct flag but may see its effect via config resolution

### WEG (`wallpaper-effects-generator`)

**App:** `cli/main.py:40` — `app = typer.Typer(name="weg")`

**Callback:** `cli/main.py:62` — `@app.callback()` defines both `--runtime` and `--container-engine` as global options (both default None).

| Command | Defined in | Consumes `--runtime`? | Consumes `--container-engine`? | Lines |
|---|---|---|---|---|
| `info` | `cli/main.py:155` | **No** | **No** | 159-166 |
| `dump-config` | `cli/main.py:169` | **No** | **No** | 174-178 |
| `dump-effects` | `cli/main.py:181` | **No** | **No** | 186-190 |
| `version` | `cli/main.py:193` | **No** | **No** | 194-196 |
| `install` | `cli/main.py:199` | **No** | **Yes** (passed to install_command) | 212 |
| `uninstall` | `cli/main.py:216` | **No** | **Yes** (passed to uninstall_command) | 223 |
| `process effect` | `cli/process.py:131` | **Yes** (via `_resolve_context`) | **Yes** (via `_resolve_context`) | 49-92 |
| `process composite` | `cli/process.py:166` | **Yes** | **Yes** | same path |
| `process preset` | `cli/process.py:201` | **Yes** | **Yes** | same path |
| `show effects` | `cli/show.py:34` | **No** | **No** | 34-38 |
| `show composites` | `cli/show.py:41` | **No** | **No** | 41-45 |
| `show presets` | `cli/show.py:48` | **No** | **No** | 48-52 |
| `show all` | `cli/show.py:55` | **No** | **No** | 55-59 |
| `batch effects` | `cli/batch.py:71` | **Yes** (via `_resolve_context`) | **Yes** (via `_resolve_context`) | 51 |
| `batch composites` | `cli/batch.py:86` | **Yes** | **Yes** | 51 |
| `batch presets` | `cli/batch.py:101` | **Yes** | **Yes** | 51 |
| `batch all` | `cli/batch.py:116` | **Yes** | **Yes** | 51 |

**How overrides flow (in `_resolve_context` at `cli/process.py:49-92`):**
- Config is resolved via `config_resolver.resolve(explicit_path=...)` — **no `cli_overrides` passed**
- `--runtime` and `--container-engine` are read from `ctx.obj` manually (lines 58-59)
- Overrides are applied by constructing new frozen dataclass instances (lines 61-86)
- This means the config-assembler-engine's `cli_overrides` mechanism is **completely dormant**

---

### Silent-Ignore Empirical Results

| Command | Output | Flag reflected? | Silent ignore? |
|---|---|---|---|
| `csg --runtime container version` | `{"version": "0.1.0"}` | — (version has no runtime concept) | **Yes** |
| `csg --container-engine podman info` | Shows `runtime.mode: local` + `container.engine` from overrides | `container-engine` **yes** (via cli_overrides), `runtime` N/A | **No** for engine |
| `csg --runtime container info` | Shows `runtime.mode: local` (not `container`!) | **No** — `--runtime` was not put in cli_overrides | **Yes** (flag parsed, processor built wastefully, but info shows wrong value) |
| `weg --runtime container info` | Shows `runtime.mode: container` | Only because user's config file has `mode = container`; CLI flag was irrelevant | **Yes** (flag parsed, stored, ignored by info) |
| `weg --container-engine podman version` | `{"message": "wallpaper-effects-generator 0.1.0"}` | **No** | **Yes** |
| `weg --container-engine podman show effects` | Shows effects catalog | **No** | **Yes** |

---

## 2. Problem Diagnosis

### 2a. Silent-Ignore Flags (21 of 23 commands combined)
9/9 CSG commands and 12/14 WEG commands accept `--runtime` or `--container-engine` from the global callback but do not meaningfully consume them. The flags parse successfully, get stored in `ctx.obj`, and are silently discarded.

### 2b. Wasteful Eager Construction (CSG only)
CSG builds the processor in the callback (`main.py:162-169`). If `--runtime container` is passed:
- `create_container_engine()` creates an `OciContainerRuntimeAdapter` wrapping a Docker/Podman client
- `create_container_processor()` builds the full container processor

This happens even for `version`, `dump-templates`, `list-backends` — commands that only read metadata.

### 2c. Misleading Info Output (CSG)
`--runtime` is consumed by the callback but NOT forwarded to `cli_overrides`. When `csg --runtime container info` runs:
- Processor is built as container (wastefully)
- `info` resolves config and shows `runtime.mode: local` (from config/default, not the CLI flag)
- User sees a contradiction: they asked for container, but it reports local

### 2d. Dormant Override System (WEG)
WEG's `AssembledConfigResolver` defines `_OVERRIDE_RULES` with `OverrideSource.CLI` for every field, but `cli_overrides=` is never passed to `_assembler.execute()` (`assembled_config_resolver.py:110-115`). The entire CLI override pathway through config-assembler-engine is unused.

### 2e. Inconsistent Architecture
Two tools, same pattern, different wiring:
- CSG overrides flow partially through `cli_overrides` (container-engine only, not runtime)
- WEG overrides bypass cli_overrides entirely, handled manually in `_resolve_context()`
- New commands have no clear convention for where to add flags

---

## 3. Options Considered

### Option A: Keep Global (Status Quo)
**Cost:** Zero migration
**Honesty:** Poor — flags appear on every command, most ignore them
**Hexagonal alignment:** Weak — eager construction in CSG violates adapter-late principles
**Verdict:** Status quo has known bugs and misleading UX. Reject.

### Option B: Sub-Typer Callback Flags
Move `--runtime` and `--container-engine` to sub-typer callbacks only on the `process` and `batch` sub-typers. Remove them from the root callback.

**Cost:** Low — only the process and batch sub-typers need them
**Honesty:** Good — flags only appear where they're consumed
**Scalability:** Medium — any new sub-typer that needs them adds a callback; easy to miss
**Maintainability:** Medium — convention must be documented and enforced
**Hexagonal alignment:** Good — processor construction deferred to sub-typer commands
**Caveat:** `install`/`uninstall` still need `--container-engine` but not `--runtime`. Under this option they'd lose the flag. Could live on individual commands.

### Option C: Per-Command Options
Add `--runtime` and/or `--container-engine` as options on individual commands that need them.

**Cost:** Medium — requires duplicating option definitions across multiple commands
**Honesty:** Excellent — flags only on commands that use them
**Scalability:** Poor — 7+ commands would need the same flag definitions; easy to diverge
**Maintainability:** Poor — DRY violation
**Hexagonal alignment:** Good — no architectural issue
**Verdict:** Too much duplication for too little gain.

### Option D: Split The Pair
Keep `--container-engine` as a global option (it goes through cli_overrides and affects config resolution), but move `--runtime` to only the commands that consume it.

**Cost:** Low
**Honesty:** Partial — `--container-engine` still appears on commands that don't directly read it, but it does affect config. `--runtime` only on process/batch.
**Scalability:** Good
**Maintainability:** Medium
**Hexagonal alignment:** Fair — partial improvement

### Option E: Config-Only (Remove Both from CLI)
Remove both flags from CLI entirely. Users set `runtime.mode` and `container.engine` in TOML config or via ENV vars (`COLORSCHEME__RUNTIME__MODE`, `WALLPAPER__CONTAINER__ENGINE`).

**Cost:** Medium clients of `install`/`uninstall` would need to
**Honesty:** Perfect — flags can't be silently ignored if they don't exist
**Scalability:** Perfect — one config mechanism for everything
**Maintainability:** High — one less thing to think about per command
**Hexagonal alignment:** Excellent — config resolution is a proper port
**Verdict:** Most architecturally pure, but breaks quick interactive use (`csg --runtime container generate` is convenient).

---

## 4. Recommended Approach

**Move `--runtime` to individual commands that need it; keep `--container-engine` on the root but wire it through the config-assembler-engine properly.**

```python
# Root callback: only --container-engine (affects config), NOT --runtime
@app.callback()
def main(ctx, ..., container_engine=None, ...):
    ctx.obj["container_engine"] = container_engine
    # cli_overrides wired for container.engine only

# process / batch sub-typers: each has its own --runtime option
@process_app.callback()
def process_callback(ctx, runtime=RuntimeMode.LOCAL):
    ctx.obj["runtime"] = runtime

# install / uninstall commands: their own --container-engine (not global)
@app.command()
def install(ctx, ..., container_engine=None):
    ...
```

### Rationale

1. **`--runtime` controls processor construction** — a command-level concern. Whether to run locally or in a container is a decision made when processing files, not when invoking the CLI generally. It has no meaning for `version`, `info`, `show`, `dump-*`, etc.

2. **`--container-engine` is a config override** — it modifies the resolved settings object, which is conceptually broader. But it should only be available where it actually does something (in commands that resolve settings AND need container engine). However, since it currently integrates with config-assembler-engine via `cli_overrides`, and future commands may also need it, keeping it as a root option and wiring it properly through `cli_overrides` is acceptable — provided it doesn't silently apply to commands that don't consume it.

3. **Fixes the CSG info discrepancy** — by removing `--runtime` from the root callback, the processor is no longer built eagerly for read-only commands. The `info` command won't promise `--runtime` in help, so there's no contradiction when it shows the config value.

4. **Activates WEG's dormant override system** — matching the recommended approach for WEG means actually passing `cli_overrides` through to `_assembler.execute()`, which aligns with the engine's design.

5. **Matches the existing architecture** — the hex architecture already separates config resolution (ports/config_resolver) from processor construction (factory). This change reinforces that boundary.

---

## 5. Before/After Shape

### CSG

| Before | After |
|---|---|
| `csg --runtime container generate image.png` | `csg generate --runtime container image.png` |
| `csg --runtime container version` | `csg version` (--runtime not listed) |
| `csg --container-engine podman info` | `csg --container-engine podman info` (unchanged) |
| `csg --container-engine podman install` | `csg install --container-engine podman` (moved to command) |

### WEG

| Before | After |
|---|---|
| `weg --runtime container process effect blur input.png` | `weg process --runtime container effect blur input.png` |
| `weg --runtime container info` | `weg info` (--runtime not listed) |
| `weg --container-engine podman version` | `weg version` (--container-engine not listed) |
| `weg --container-engine podman install` | `weg install --container-engine podman` |

---

## 6. Architecture Impact

| Layer | Impact |
|---|---|
| **Domain** | **None.** No domain models, enums, or services change. |
| **Ports** | **None.** All port interfaces unchanged. |
| **Adapters** | **None.** No adapter code changes. |
| **Factory** | **CSG only.** `build_deps()` no longer needs a default `LocalProcessor` in deps; processor built lazily on demand. |
| **CLI** | **Significant.** Root callback loses `--runtime` in both tools. CSG gains lazy processor construction. WEG gains `cli_overrides` wiring through config-assembler-engine. `process`/`batch` sub-typers gain `@callback()` for `--runtime`. `install`/`uninstall` gain their own `--container-engine` option. |
| **Config resolution** | **WEG only.** `AssembledConfigResolver.resolve()` gains `cli_overrides` parameter (matching CSG's interface). Override rules already exist; parameter just needs to be plumbed through. |

### Layer Diagram

```
Before (CSG):
  Root callback: --runtime --container-engine
       ↓                      ↓
  Eager processor       cli_overrides → config-assembler-engine
  (all commands)              ↓
                         resolved settings

After (CSG):
  Root callback: --container-engine
       ↓
  cli_overrides → config-assembler-engine
       ↓
  resolved settings

  process/batch callback: --runtime
       ↓
  lazy processor (only when needed)

  install/uninstall: --container-engine (own option)
       ↓
  direct read from ctx.obj
```

```
Before (WEG):
  Root callback: --runtime --container-engine
       ↓           ↓
  ctx.obj store  ctx.obj store
       ↓           ↓
  _resolve_context() manual override bypasses config-assembler-engine

After (WEG):
  Root callback: --container-engine
       ↓
  cli_overrides → config-assembler-engine (finally used!)
       ↓
  resolved settings with overrides

  process/batch callback: --runtime
       ↓
  _resolve_processor() uses runtime from ctx.obj
```

---

## 7. Migration Notes

### Tests

| File | Lines | Impact |
|---|---|---|
| `csg/tests/unit/cli/test_runtime_mode.py` | 85, 96, 107, 118, 130 | Tests that pass `--runtime`/`--container-engine` to `version` must move to command-level or be removed |
| `csg/tests/unit/cli/test_install_command.py` | 130 | `--container-engine podman` passed at root level before `install` — no change (stays root) |
| `csg/tests/test_user_journey.sh` | 161, 194 | Line 161 checks `--help` for `--runtime` (must update assertion). Line 194 passes `--runtime local info` — remove `--runtime` |
| `weg/tests/test_cli.py` | 128-131 | Passes `--runtime container info` — remove `--runtime` from the invoke args |
| `weg/tests/unit/cli/test_process_commands.py` | 204, 230, 244, 260, 288, 290 | Tests pass `--container-engine` at root before `process` subcommand — move to after `process` or change to sub-typer callback |

### Docs
- `--help` output changes for all commands (fewer global options)
- README examples showing `csg --runtime container ...` need updating

### Scripts
- Any shell scripts or CI pipelines using `csg --runtime container ...` or `weg --runtime container ...` as global flags need updating to pass them at the command/sub-typer level
- `csg --runtime container info` (used in `test_user_journey.sh:194`) is particularly likely in user scripts

### Migration Order
1. Add `--runtime` to `process`/`batch` sub-typer callbacks (both tools)
2. Add `--container-engine` to `install`/`uninstall` command options (both tools)
3. Remove `--runtime` from root callback (both tools)
4. Wire `cli_overrides` through WEG's `AssembledConfigResolver.resolve()`
5. Remove `--container-engine` from root callback in WEG (optional — could stay since it affects config)
6. Update CSG factory to build processor lazily
7. Update tests
8. Update docs/scripts

---

**Do not write any implementation code.** This is a design investigation only.
