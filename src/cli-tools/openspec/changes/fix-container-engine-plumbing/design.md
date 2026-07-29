## Context

CSG has two container engine flags: global `--container-engine` (parsed by callback) and install's `--engine` (default `docker`). The callback never stores `container_engine` in `ctx.obj` or `cli_overrides`, so install never sees the global flag. WEG solved this by having the callback store the value in `ctx.obj["container_engine"]` and having `install` read it from there — no duplicate flag.

Affected files:
- `src/color_scheme_generator/cli/main.py` (callback)
- `src/color_scheme_generator/cli/install_cmd.py`
- `src/color_scheme_generator/cli/uninstall_cmd.py`

## Goals / Non-Goals

**Goals:**
- `csg --container-engine podman install` builds images into Podman
- `csg --container-engine podman generate` (with `--runtime container`) checks the same runtime
- No duplicate `--engine` / `--container-engine` flags
- Backward compatible for anyone using `csg install` (defaults to docker as before)
- Match WEG's proven pattern exactly

**Non-Goals:**
- Other commands like `dump-config`, `info`, `version` — they don't use the container engine
- The `process`/`show`/`batch` commands already get engine through the callback's CONTAINER path

## Decisions

**Decision 1: Store container_engine in ctx.obj (match WEG)**
- WEG stores it in `ctx.obj["container_engine"]` at callback line 123
- CSG will do the same — one line addition
- Install and uninstall read it from `ctx.obj.get("container_engine")`

**Decision 2: Also add to cli_overrides**  
- The settings system already has `OverrideRule("container.engine", {CLI, ENV})` in `config_resolver.py`
- Adding `cli_overrides["container.engine"] = container_engine.value` makes the resolved settings contain the correct engine
- This allows any code that reads `settings.container.engine` to get the right value
- WEG doesn't do this (WEG has no override rules for container settings), but CSG's settings system supports it

**Decision 3: Remove install's --engine parameter**
- Install currently has `engine: ContainerEngine = typer.Option(ContainerEngine.DOCKER, "--engine", ...)`
- Remove this parameter entirely
- Fallback logic: `ctx.obj.get("container_engine") or settings.container.engine` or `ContainerEngine.DOCKER`
- This eliminates the confusing two-flag situation

**Alternative considered:** Keep `--engine` on install but have it default to `ctx.obj["container_engine"]` when the global flag was passed. Rejected because it adds complexity and still leaves two flags for the same thing.

## Risks / Trade-offs

- **Backward compatibility**: Anyone scripting `csg install --engine podman` will break. Mitigation: check if any scripts use this. The install command is new (v3), likely not heavily scripted yet.
- **Uninstall also hardcodes**: `uninstall_cmd.py` line 47 hardcodes `ContainerEngine.DOCKER`. It should also read from `ctx.obj`. Same fix applied.
