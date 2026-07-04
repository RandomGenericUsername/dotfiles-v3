## Why

OCI subcommands are scattered string literals across all four managers: `"run"`, `"build"`, `"inspect"`, `"tag"`, `"push"`, `"pull"`, `"rmi"`, `"rm"`, `"exec"`, `"logs"`, `"stop"`, `"start"`, `"restart"`, `"prune"`, `"create"`, `"connect"`, `"disconnect"`, `"list"`, `"image"`, `"container"`, `"volume"`, `"network"`. A typo (`"inspec"`) is uncatchable at static typecheck. The codebase already enums `RuntimeKind`, `ContainerState` — omitting subcommands is inconsistent.

## What Changes

- Add `Subcommand(str, Enum)` to `domain/enums.py` with the ~20 members.
- Migrate manager adapters to use `Subcommand.X.value` at cmd-construction call sites.
- **Adapter-internal only** — not re-exported from `oci_runtime/__init__.py`.

## Capabilities

### New Capabilities

- `oci-subcommand-enum`: a `Subcommand(str, Enum)` SHALL exist in `domain/enums.py`; managers SHALL use `.value` at call sites; the enum SHALL NOT be re-exported from the public API.

## Impact

- **Code**: `domain/enums.py` (add enum), all four `adapters/managers/*.py` (replace string literals).
- **Tests**: verify enum members match all string literals used; verify `Subcommand.INSPECT.value == "inspect"`.
- **Risk**: low — every manager call site changes; the public surface is unchanged.