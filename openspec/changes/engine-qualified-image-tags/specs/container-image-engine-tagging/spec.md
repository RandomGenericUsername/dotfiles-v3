# Container Image Engine Tagging

## Status: ADDED

## Why

Container images built by WEG and CSG share identical tags across both docker and podman engines, making it impossible to distinguish which engine an image was built for. Rebuilding for a different engine silently overwrites the existing image.

## What

A shared helper `engine_qualified_image(name, engine, tag, registry=None)` in `oci_runtime` produces image names of the form `{registry/}{name}-{engine}:{tag}`. This suffix is always applied, including for the default docker engine.

### WEG

- `cli/install.py` `_build_image_name` → delegates to `engine_qualified_image`
- `cli/uninstall.py` `_build_image_name` → delegates to `engine_qualified_image`
- `adapters/container_processor.py` `_resolve_image` → delegates to `engine_qualified_image`
- No signature changes needed — `ContainerSettings.engine` is already populated by existing override plumbing

### CSG

- `cli/_helpers.py` `build_image_name` → accepts `engine` parameter, calls `engine_qualified_image`
- `cli/install_cmd.py` → captures `engine_value` before variable shadowing, threads into base image and backend build calls
- `cli/uninstall_cmd.py` → same pattern
- `adapters/container_processor.py` `_select_image` → uses `engine_qualified_image` with engine from settings or processor-level override
- `adapters/dry_run_processor.py` `_build_image_name` → uses `engine_qualified_image`
- `cli/main.py` `generate()` → passes `engine_obj.value` into processor construction

## API

```python
def engine_qualified_image(
    name: str,
    engine: str,
    tag: str,
    registry: str | None = None,
) -> str:
```

- `name`: base image name (e.g. "weg", "csg-color-scheme-base")
- `engine`: lowercase engine string ("docker" or "podman")
- `tag`: image tag (e.g. "latest")
- `registry`: optional registry URL

Returns: `{registry/}{name}-{engine}:{tag}`

## Examples

| Input | Output |
|-------|--------|
| `("weg", "docker", "latest")` | `weg-docker:latest` |
| `("weg-managed", "podman", "latest", "ghcr.io")` | `ghcr.io/weg-managed-podman:latest` |
| `("csg-color-scheme-base", "podman", "latest")` | `csg-color-scheme-base-podman:latest` |
| `("weg", "", "latest")` | `ValueError` |
