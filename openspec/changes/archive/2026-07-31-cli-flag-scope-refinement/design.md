## Context

CSG and WEG are two CLI tools sharing the same config-assembler-engine library and a similar hexagonal architecture. Both have a typer `@app.callback()` that defines `--runtime` and `--container-engine` as global options. The investigation confirmed:

- **21 of 23 commands** accept these flags but silently ignore them. Only CSG `generate` and WEG `process/*`/`batch/*`/`install`/`uninstall` meaningfully consume either flag.
- **CSG builds the processor eagerly** in the root callback for ALL commands, wasting resources on `version`, `dump-*`, `list-backends`, etc.
- **CSG's `--runtime` and `--container-engine` have non-None defaults** (`LOCAL`, `DOCKER`), making TOML/ENV settings unreachable — the CLI flag always overrides.
- **WEG stores flags in `ctx.obj`** and applies them post-resolution via manual mutation, bypassing the config-assembler-engine's `cli_overrides` mechanism entirely (the mechanism exists in code but is never called).
- **WEG `process` sub-typer** has redundant `-e`/`-c`/`-p` override options on each leaf command where the positional argument already serves the same purpose.

## Goals / Non-Goals

**Goals:**
- Every CLI flag appears in exactly the scope where it is consumed — no silent ignores
- Consistent architecture between CSG and WEG for how runtime/engine flags flow
- CSG honors TOML/ENV runtime settings as baseline (like WEG already does)
- WEG's dormant `cli_overrides` mechanism is activated
- Redundant options eliminated
- DRY maintained via shared option definitions

**Non-Goals:**
- Changing any domain model, port interface, or adapter (beyond the config-resolver call site)
- Changing the config-assembler-engine library itself
- Adding new commands or capabilities
- Changing output-format, verbosity, config-path, templates-dir/effects-path flags (they stay cross-cutting at root)
- Env var or TOML config format changes

## Decisions

### D1: Flag scoping strategy — sub-typer callbacks for families, leaf options for singletons

**Choice:** Sub-typer callbacks for WEG `process`/`batch` families; leaf options for CSG `generate` and both tools' `install`/`uninstall`.

**Alternatives considered:**
- *All per-leaf (Option C from investigation):* Works but duplicates option declarations across 7+ leaves in WEG `process`/`batch`. Mitigated by shared option factories (see D2).
- *Keep `--container-engine` global (Option E split):* Leaves it on commands that don't consume it. Violates the "scope matches consumers" principle.
- *All on root (status quo):* The 21-of-23 silent-ignore problem, addressed in the investigation.

**Why this choice:** WEG's `process` and `batch` are logical families — every member consumes both flags. The sub-typer callback is the natural scope for "all commands in this group." CSG has no sub-typer grouping for `generate` (it's standalone), and `install`/`uninstall` are singleton leaves, so leaf options are the natural choice.

### D2: Centralized option definitions (`cli/options.py`)

**Choice:** Each tool gets a `cli/options.py` module exporting `runtime_opt` and `engine_opt` constants (instances of `typer.Option`).

```python
# cli/options.py
RUNTIME_OPT = typer.Option(None, "--runtime", ...)
ENGINE_OPT  = typer.Option(None, "--container-engine", ...)
```

Leaves import: `from .options import RUNTIME_OPT, ENGINE_OPT`

**Alternatives considered:**
- *Decorator factory:* A `with_runtime(fn)` wrapper that injects the option. Typer inspects function signatures for options; a decorator that adds a keyword argument to `__annotations__` would work but is non-obvious and breaks static analysis.
- *Inline repetition:* The investigation noted "Typer supports this but violates DRY." The factory module solves this cleanly with zero magic.

**Why this choice:** Single import, zero duplication, works with typer's signature introspection (the constant IS a `typer.Option` instance, same as inline), easy to find and audit.

### D3: `--runtime` defaults to `None` (optional) in both tools

**Choice:** Both tools use `None` as the default for `--runtime`, mirroring WEG's current behavior. CSG changes from `RuntimeMode.LOCAL` (non-None) to `None`.

**Rationale:** A non-None default makes it impossible for the user to express "use whatever TOML/ENV says" via CLI omission. The omission always resolves to the default value, which overrides config. With `None`, the absence of the flag means "don't override," and the TOML/ENV value is used as-is.

**Impact on CSG:** The `generate` command body must handle the case where `--runtime` is not passed by reading from resolved `settings.runtime.mode` instead of defaulting to LOCAL. This aligns with WEG's existing `_resolve_processor()` pattern.

### D4: `--container-engine` defaults to `None` in both tools (CSG change)

**Choice:** Both tools use `None` as the default for `--container-engine`. CSG changes from `ContainerEngine.DOCKER` (non-None) to `None`. This fixes the investigation-reported bug where TOML `container.engine` was silently ignored.

**Impact on CSG:** The `generate`, `install`, `uninstall` command bodies must handle `None` by falling back to `settings.container.engine` (from TOML/ENV), then to a hardcoded default (DOCKER). WEG already does this.

### D5: WEG activates `cli_overrides` plumbing

**Choice:** WEG `AssembledConfigResolver.resolve()` gains a `cli_overrides` parameter. The `process`/`batch` sub-typer callbacks (and `install`/`uninstall` leaves) build the `cli_overrides` dict from their parsed flags and pass it to `resolve()` instead of the current post-resolution object mutation in `_resolve_context()`.

**Current code (`_resolve_context` in `process.py:49-92`):**
```python
settings = config_resolver.resolve(explicit_path=...)
runtime_override = ctx.obj.get("runtime")
engine_override = ctx.obj.get("container_engine")
# mutate settings objects manually ...
```

**After:**
```python
cli_overrides = {}
if runtime_override is not None:
    cli_overrides["runtime.mode"] = runtime_override.value
if engine_override is not None:
    cli_overrides["container.engine"] = engine_override.value
settings = config_resolver.resolve(explicit_path=..., cli_overrides=cli_overrides)
```

The override rules in `assembled_config_resolver.py` already declare `OverrideSource.CLI` for these fields — the mechanism is designed for this; it just wasn't plumbed.

### D6: CSG adapts WEG's lazy processor pattern

**Choice:** CSG's root callback no longer builds any processor. The `generate` command builds it on demand, exactly like WEG's `_resolve_processor()`.

**Current (`main.py:162-169`):**
```python
if runtime is RuntimeMode.LOCAL and deps.processor is None:
    deps.processor = create_local_processor(...)
elif runtime is RuntimeMode.CONTAINER:
    container_runtime = create_container_engine(engine=container_engine)
    deps.processor = create_container_processor(...)
```

**After:** `generate` gains `--runtime` and `--container-engine` as local options. The command body:
```python
def generate(ctx, ..., runtime=None, container_engine=None):
    settings = config_resolver.resolve(explicit_path=..., cli_overrides=cli_overrides)
    runtime_mode = runtime or settings.runtime.mode
    if runtime_mode == RuntimeMode.LOCAL:
        processor = create_local_processor(...)
    else:
        engine = container_engine or settings.container.engine or ContainerEngine.DOCKER
        processor = create_container_processor(...)
    result = processor.process_generate(request, settings)
```

### D7: Drop redundant `-e`/`-c`/`-p` override options from WEG process

**Choice:** Remove `effect_name`/`-e`, `composite_name`/`-c`, `preset_name`/`-p` from the `process effect|composite|preset` commands. The positional `name` argument is the canonical input.

**Rationale:** These are pure aliases — the body immediately resolves `name = effect_name or name`. They add help-text clutter and maintenance surface for zero behavioral value.

**Current (`process.py:131-151`):**
```python
def effect(ctx, name: str = typer.Argument(...),
           effect_name: str | None = typer.Option(None, "-e", "--effect", ...)):
    name = effect_name or name
```

**After:**
```python
def effect(ctx, name: str = typer.Argument(...)):
    ...

def composite(ctx, name: str = typer.Argument(...)):
    ...

def preset(ctx, name: str = typer.Argument(...)):
    ...
```

### D8: Root callback retains only cross-cutting flags

**Choice:** Both tools' `@app.callback()` retains these flags verbatim:
- `--config` (config path — affects all config-resolving commands)
- `--templates-dir` (CSG) / `--effects` (WEG) — affects all commands that resolve those resources
- `--output-format` — affects all output-emitting commands
- `--verbose`/`-v`, `--quiet`/`-q` — affects all commands' log level

These flags are removed from root:
- `--runtime` → moves to leaf/sub-typer scope
- `--container-engine` → moves to leaf/sub-typer scope

**Rationale:** Config paths, output rendering, and logging are genuinely cross-cutting — they change HOW the tool operates globally. Runtime/engine flags change WHAT ACTION a particular processing command takes.

## Risks / Trade-offs

- **[Discoverability]** Users typing `csg --help` won't see `--runtime` in global options anymore. They must type `csg generate --help` to discover it. **Mitigation:** This is the correct behavior — the flag only makes sense in the context of `generate`. Industry precedent (docker, git, kubectl) follows this same pattern.

- **[Migration churn]** Shell scripts and CI pipelines that use global flags must be updated. **Mitigation:** 5 test files affected — documented in the investigation. No external consumers beyond these tools' own test suite.

- **[CSG `show` loses processor override]** Currently `show` uses the processor built in the root callback. Under lazy construction, `show` won't have access to a pre-built processor. **Decision:** `show` builds its own processor from resolved config (same as WEG's leaf pattern). The type/dispatch logic moves into leaf commands, not the root callback.

- **[Config-resolver re-resolution]** WEG resolves config on every leaf invocation (in `_resolve_context()`). This is existing behavior, not new. Not an issue — config resolution is read-only and fast.

- **[CSG `info`/`dump-config` lose `cli_overrides` for container-engine]** Currently they pass `cli_overrides` which includes `container.engine`. After refactoring, root `cli_overrides` won't include runtime/engine. **Decision:** These commands are read-only and don't need engine info for behavior — they show the resolved settings object. The engine value comes from TOML/ENV, not CLI. This is actually more correct (shows what WOULD be used, not what was typed on a non-processing command).
