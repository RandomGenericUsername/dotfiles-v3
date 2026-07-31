## Context

Both WEG and CSG have container processors that build a CLI command and
pass it into a container for execution:

```
┌───────────────────┐        argv         ┌────────────────────┐
│  ContainerAdapter │ ──────────────────→ │  Container image   │
│  (host side)      │                     │  (runs CLI innner) │
│                   │                     │                    │
│  _build_weg_cmd() │  "weg <flags>       │  weg <flags>       │
│                   │   process effect …" │  process effect … │
│  inner_command[]  │  "csg <flags>       │  csg <flags>       │
│                   │   generate …"       │  generate …"       │
└───────────────────┘                     └────────────────────┘
```

The argv includes CLI flags that configure the tool's behavior inside the
container — which config file to read, which effects file to load,
which runtime mode to use. These flags live at a specific Typer/Click
scope (root, sub-typer callback, or leaf command), and that scope can change
as the CLI surface evolves.

**The coupling**: the adapter must know the exact flag scope of every
CLI option it includes in the argv. This knowledge is not derived from
shared code — it's hand-positioned in a list literal inside the adapter.
Any change to the CLI's flag-scope layout requires a corresponding change
in the adapter, but nothing enforces this correspondence.

The `cli-flag-scope-completion` change is a clear example: it moved
`--config` and `--effects` from root to sub-typer callbacks but never
touched `_build_weg_command`. The adapter emits the old root-level form,
the CLI rejects it — "No such option: --config".

## Goals / Non-Goals

### Goals

- Decouple the container processor's in-container argv from CLI flag-scope
  decisions in both WEG and CSG.
- Remove all config/resource-path flags (`--config`, `--effects`) from
  the in-container argv. These values are already mounted as files at
  well-known container paths — make discovery implicit via env vars.
- Remove runtime-mode flags (`--runtime`) from the in-container argv
  (CSG only; WEG already does not pass `--runtime`). The serialized
  settings.toml already has `runtime.mode = local` baked in.
- Add a regression test that validates the adapter's argv against the
  live CLI parser, catching future drift at test time.
- Set HOME/XDG vars in the container environment (CSG already does this;
  WEG does not — a gap for non-writable home directory and XDG fallback).

### Non-Goals

- Changing how the CLI parses flags on the host side. Flag-scope
  positioning of `--config`/`--effects` on the host is correct and
  unchanged.
- Changing the `oci_runtime` library or `RunConfig` API.
- Changing any domain or port logic outside the adapters.
- Building or modifying container images.

## Decisions

### D1: Environment variables over CLI flags for in-container configuration

**Choice**: Replace CLI flags (`--config`, `--effects`, `--runtime`) in
the in-container argv with environment variables passed via
`RunConfig.environment`.

**Rationale**: The `config-assembler-engine` already supports env-var-based
discovery via `EnvPathStrategy` (for file paths) and `OverrideMatchingService`
(for field overrides). Both WEG and CSG already use this mechanism on the
host side — using env vars inside the container is the same mechanism, not
a new one.

The env var names are already documented in the CLI help text at
`cli/main.py`:

| Tool | Discovery | Env Var | Value inside container |
|------|-----------|---------|----------------------|
| WEG | settings.toml path | `WALLPAPER_CONFIG_FILE_PATH` | `/weg-config/settings.toml` |
| WEG | effects.yaml path | `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` | `/weg-effects/effects.yaml` |
| WEG | runtime.mode override | `WALLPAPER__RUNTIME__MODE` | `local` |
| CSG | settings.toml path | `COLORSCHEME_CONFIG_FILE_PATH` | `/csg-config/settings.toml` |
| CSG | runtime.mode override | `COLORSCHEME__RUNTIME__MODE` | `local` |
| CSG | templates dir | `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` | `/templates` |
| both | home dir | `HOME` | `/tmp` |
| both | XDG config home | `XDG_CONFIG_HOME` | `/tmp/.config` |
| both | XDG cache home | `XDG_CACHE_HOME` | `/tmp/.cache` |

**Env var formula reference** (from `config-assembler-engine` source):

- File paths: `{env_prefix}_{var}` where `EnvPathStrategy(var="CONFIG_FILE_PATH")`
  → `WALLPAPER_CONFIG_FILE_PATH` (prefix `WALLPAPER` + `_` + var `CONFIG_FILE_PATH`)
- Field overrides: `{env_prefix}__{DOTTED_PATH}` where
  `OverrideMatchingService.ENV_SEPARATOR = "__"` → replaces `__` with `.`
  → `WALLPAPER__RUNTIME__MODE` → `runtime.mode`

**Mapping to `_ALL_SETTINGS_FIELDS`** (WEG's registered override fields,
all accepting `OverrideSource.ENV`):

| Field path | Env var | Value in container |
|------------|---------|-------------------|
| `runtime.mode` | `WALLPAPER__RUNTIME__MODE` | `local` |
| `container.engine` | `WALLPAPER__CONTAINER__ENGINE` | `docker` |

Only `runtime.mode = local` is necessary for safety — the serialized
settings.toml already encodes it. Setting it explicitly via env adds
belt-and-suspenders.

### D2: Interface contract test validates adapter argv against live CLI

**Choice**: For each tool, a test constructs the adapter's in-container
argv via the production code path, strips the program name, and passes
the remaining argv through `typer.testing.CliRunner` against the real
CLI `app`.

**Rationale**: This is the only way to catch flag-scope drift between the
adapter and the CLI at test time. The test doesn't need to run the
processor — it patches `_resolve_processor` and `_resolve_context` to
return mocks. What it validates is the parser's acceptance of the argv
shape.

```
          ┌──────────────────────┐
          │  adapter._build_    │
          │  weg_command(args)  │  returns ["weg", "process",
          └────────┬─────────────┘           "--config", X, …]
                   │
                   │ cmd = result[1:]   (strip "weg")
                   ▼
          ┌──────────────────────┐
          │  CliRunner.invoke    │── parses argv through real CLI
          │  (app, cmd)          │── if --config is misplaced,
          └────────┬─────────────┘     CLI says "No such option"
                   │
                   │ assert exit_code == 0
                   ▼
          ┌──────────────────────┐
          │  FAIL: adapter       │
          │  argv out of sync    │
          │  with CLI surface    │
          └──────────────────────┘
```

The test pattern is parameterizable across the three subcommand types:

- `process effect blur input.png -o /output --param radius=0x8`
- `process composite blur-resize input.png -o /output`
- `process preset social input.png -o /output`

### D3: CSG `_CONTAINER_ENV` extended, WEG gets new `_CONTAINER_ENV`

**Choice**: WEG gains a `_CONTAINER_ENV` dict (module-level constant,
like CSG's). CSG's existing `_CONTAINER_ENV` gains
`COLORSCHEME__RUNTIME__MODE=local`.

**Rationale**: Consolidates all container-environment configuration in a
single named constant. Test asserts `env == _CONTAINER_ENV` using a
single reference, not a hardcoded dict.

**WEG `_CONTAINER_ENV`**:
```python
_CONTAINER_ENV = {
    "HOME": "/tmp",
    "XDG_CONFIG_HOME": "/tmp/.config",
    "XDG_CACHE_HOME": "/tmp/.cache",
    "WALLPAPER_CONFIG_FILE_PATH": "/weg-config/settings.toml",
    "WALLPAPER_EFFECTS_CONFIG_FILE_PATH": "/weg-effects/effects.yaml",
    "WALLPAPER__RUNTIME__MODE": "local",
}
```

**CSG `_CONTAINER_ENV`** (adds one key):
```python
_CONTAINER_ENV = {
    "HOME": "/tmp",
    "XDG_CONFIG_HOME": "/tmp/.config",
    "XDG_CACHE_HOME": "/tmp/.cache",
    "COLORSCHEME_CONFIG_FILE_PATH": "/csg-config/settings.toml",
    "COLORSCHEME_TEMPLATES_TEMPLATES_DIR": "/templates",
    "COLORSCHEME__RUNTIME__MODE": "local",         # NEW
}
```

### D4: Fix CSG `ContainerRuntimePort` protocol to declare `environment`

**Choice**: Add `environment: dict[str, str] | None = None` to the
`run()` method signature in the `ContainerRuntimePort` protocol.

**Rationale**: The protocol (port) declares what the adapter (concrete
implementation) must accept. `OciContainerRuntimeAdapter.run()` already
accepts `environment` as an optional keyword param, but the protocol
never declared it. This means:

1. A static type checker (mypy, pyright) flags the
   `self._container_runtime.run(environment=_CONTAINER_ENV, ...)` call
   as an unexpected keyword argument.
2. Anyone implementing a new adapter wouldn't know `environment` is
   an expected parameter.
3. It's a hexagonal-architecture leak — the port interface doesn't
   reflect the actual contract.

The default `None` keeps it backward-compatible: any existing or future
adapter that doesn't use environment simply omits the parameter.

### D5: Remove dead `output_name` from WEG `_build_weg_command`

**Choice**: Delete the unused `output_name` assignment at line 153 of
`container_processor.py`.

**Rationale**: Dead code. `output_name` is computed but never referenced.

## Risks / Trade-offs

### The env-var approach is strictly more robust but changes failure signature

Currently, a malformed argv yields a clear CLI error in the container log:
`"No such option: --config"`. With env vars, a similarly wrong env var
name would be silently ignored — the config resolver would not find the
file and fall through the discovery chain to XDG or bundled defaults.

**Mitigation:** The test suite mitigates this: `test_passes_expected_environment`
asserts the exact env dict, and the interface contract test validates the argv.

### Container image staleness remains a risk for env-var features

If an image was built from a version of the source that didn't yet support
a particular env var (e.g., `WALLPAPER__RUNTIME__MODE`), that env var
would be silently ignored. However, `EnvPathStrategy` and
`OverrideMatchingService` are in the `config-assembler-engine` shared
library, which has been present since the project's inception. The env var
names used in this change all follow the documented scheme from the CLI
help text, which has been stable.

**Mitigation:** None needed — the feature is as old as the codebase.

### Interface contract test adds a real CLI import to the test

The test imports the live `app` from `cli/main.py` and patches processor
resolution. This means changes to the CLI's import graph or constructor
signatures can break the test's import chain.

**Mitigation:** This is a feature, not a bug — if the CLI's import graph
changes in a way that makes the parser unreachable, the test reflects
that faithfully. The WEG test patches `_resolve_processor` and
`_resolve_context`; the CSG test patches `create_local_processor` and
`create_container_processor` at `cli.main` (since CSG's `generate`
command inlines factory calls rather than using a helper).

### oci-runtime environment propagation is fully validated

The env var chain has been traced end-to-end in both tools:

- **WEG**: `RunConfig.environment` → `CliContainerManager.run()` iterates
  the mapping at `oci_runtime/.../container.py:125-126` → `-e KEY=VAL`
  on docker/podman CLI. Test at `test_manager_commands.py:305-373` confirms.
- **CSG**: `_CONTAINER_ENV` → `OciContainerRuntimeAdapter.run()` at
  `oci_container_runtime.py:50` → `RunConfig(environment=...)` →
  same `CliContainerManager.run()` path. Test at
  `test_container_processor.py:350` asserts `env == _CONTAINER_ENV`.

The protocol was previously missing `environment` in its `run()` signature
(see D4). The protocol fix makes this chain fully explicit and type-safe.

## Final state

### WEG — in-container argv before/after

```
Before:  weg --config /weg-config/settings.toml --effects /weg-effects/effects.yaml process effect blur /input/x.png -o /output --param radius=0x8
                                           ↑ stale root-level flags ↑
After:   weg process effect blur /input/x.png -o /output --param radius=0x8
           ↑ no config/effects flags — handled by env vars ↑
```

And `RunConfig` gains:
```python
environment={
    "HOME": "/tmp",
    "XDG_CONFIG_HOME": "/tmp/.config",
    "XDG_CACHE_HOME": "/tmp/.cache",
    "WALLPAPER_CONFIG_FILE_PATH": "/weg-config/settings.toml",
    "WALLPAPER_EFFECTS_CONFIG_FILE_PATH": "/weg-effects/effects.yaml",
    "WALLPAPER__RUNTIME__MODE": "local",
}
```

### CSG — in-container argv before/after

```
Before:  csg --runtime local generate /input/x.png --backend custom --param saturation=1.0 -o /output
             ↑ stale root-level flag ↑
After:   csg generate /input/x.png --backend custom --param saturation=1.0 -o /output
```

And `_CONTAINER_ENV` gains:
```python
"COLORSCHEME__RUNTIME__MODE": "local",
```

### Schematic of decoupling

```
    BEFORE:                       AFTER:

    CLI flag move ──breaks──→ adapter     env var ──(inert)──→ CLI flag move
                                                                  ▲
                                                                  │
                                                          adapter unaffected
```

The env var path and the CLI flag path are independent channels.
Changes to CLI flag scope don't affect env var discovery, and env var
additions don't require CLI changes. The adapter no longer needs to
know how the CLI positions its flags — it uses the env var channel
which is scope-agnostic.
