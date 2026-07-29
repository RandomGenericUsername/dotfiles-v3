## 1. Callback plumbing

- [x] 1.1 Store `container_engine` in `ctx.obj["container_engine"]` in the callback (`main.py`)
- [x] 1.2 Add `container_engine` to `cli_overrides` as `"container.engine"` so settings resolve it

## 2. Install command

- [x] 2.1 Remove `--engine` parameter from install command signature (`install_cmd.py`)
- [x] 2.2 Read engine from `ctx.obj.get("container_engine")` with fallback to `settings.container.engine` then `ContainerEngine.DOCKER`
- [x] 2.3 Pass engine to `create_container_engine()` instead of the removed param

## 3. Uninstall command

- [x] 3.1 Read engine from `ctx.obj.get("container_engine")` instead of hardcoded `ContainerEngine.DOCKER` (`uninstall_cmd.py`)
