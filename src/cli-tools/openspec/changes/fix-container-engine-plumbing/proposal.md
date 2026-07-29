## Why

The global `--container-engine` flag is silently discarded by the callback and has no effect on the `install` command, which has its own `--engine` flag defaulting to `docker`. This means `csg --container-engine podman install` builds images into Docker, then `csg --runtime container --container-engine podman generate` looks for them in Podman and fails with `ContainerImageNotFoundError`. WEG handles this correctly — the same pattern should be used here.

## What Changes

- **Global callback**: Store `container_engine` in `ctx.obj["container_engine"]` so subcommands can read it
- **Global callback**: Add `container_engine` to `cli_overrides` so settings resolve it via `container.engine` override
- **Install command**: Remove its own `--engine` parameter, read engine from `ctx.obj["container_engine"]` instead
- **Uninstall command**: Read engine from `ctx.obj["container_engine"]` (currently hardcodes Docker)

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

(none — no spec-level requirement changes, only implementation plumbing)

## Impact

- `src/color_scheme_generator/cli/main.py` — callback stores container engine in ctx.obj and cli_overrides
- `src/color_scheme_generator/cli/install_cmd.py` — remove `--engine` param, read from ctx.obj
- `src/color_scheme_generator/cli/uninstall_cmd.py` — read engine from ctx.obj
