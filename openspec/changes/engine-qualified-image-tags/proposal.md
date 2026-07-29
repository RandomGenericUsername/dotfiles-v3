## Why

`weg install` and `csg install` both build container images keyed off `--container-engine` (docker or podman), but the image *name* never references the engine. Both engines land in image repositories under identical tags — `weg:latest`, `color-scheme-base:latest`, `csgcolor-scheme-custom:latest` — so `docker images` and `podman images` are indistinguishable, and rebuilding for one engine silently overwrites (or shadows) the other engine's image. There is no operational way to tell whether a given `color-scheme-base:latest` was built for docker or podman, nor to keep both engine variants installed side-by-side.

Two related defects surfaced during investigation and are fixed in the same change:

- CSG backend image names concatenate the `csg` prefix with the `color-scheme-` literal with no separator, producing `csgcolor-scheme-custom:latest` (no hyphen). The base image carries no prefix at all (`color-scheme-base:latest`). The architecture plan documented `csg-color-scheme-*` (hyphenated) and `color-scheme-*` — neither matches what shipped. Existing tests reference yet a third spelling (`csg-color-scheme-custom`). Every surface is inconsistent.
- The image-name string is constructed independently in three (WEG) and three (CSG) places with no shared helper, each duplicating the `registry/name:tag` assembly. Any future naming change must be applied to all copies in lockstep or the run path fails to find the image built by install.

## What Changes

Move the container *engine* into the image **name** (not the tag), always applied (including the docker default), so every built image is unambiguously qualified by the engine it targets. Centralize name construction in a single shared helper in `oci-runtime`, normalize CSG backend/base naming to a hyphenated `csg-color-scheme-*` scheme, and reconcile it with the static `FROM` references in CSG's backend Dockerfiles.

**Specific changes:**

1. **Shared naming helper in `oci-runtime`.** Add `oci_runtime.domain.naming.engine_qualified_image(name, engine, tag, registry=None) -> str` producing `{registry/}{name}-{engine}:{tag}`. Export it from the `oci_runtime` package. This is the single source of truth; both tools call it instead of re-assembling the string locally.

2. **WEG uses the helper at all three construction sites:**
   - `cli/install.py` `_build_image_name` (build path)
   - `cli/uninstall.py` `_build_image_name` (remove path — stays symmetric with build)
   - `adapters/container_processor.py` `_resolve_image` (run path — must resolve to the same engine-qualified name install produced)
   
   With `image_name="weg"`, `image_tag="latest"`, engine `podman` → `weg-podman:latest`; with registry → `ghcr.io/weg-managed-podman:latest`. `ContainerSettings`/schema/`settings.toml` defaults are unchanged — the engine qualifier is computed, never persisted.

3. **CSG uses the helper and normalizes names to a hyphenated scheme:**
   - `cli/_helpers.py` `build_image_name` → `engine_qualified_image(f"{prefix}-color-scheme-{backend.image_suffix}", engine, tag)` → `csg-color-scheme-custom-podman:latest`. Needs the resolved `engine` threaded in from install/uninstall callers.
   - `cli/install_cmd.py` base literal `"color-scheme-base:latest"` → `engine_qualified_image(f"{prefix}-color-scheme-base", engine, tag)` → `csg-color-scheme-base-podman:latest`. Capture the enum value before the local `container_engine` variable is shadowed by the runtime object.
   - Runtime path mirrors `adapters/container_processor.py` `_select_image` and `adapters/dry_run_processor.py` `_build_image_name` produce the same names so `csg generate` finds the installed image.

4. **CSG backend Dockerfile `FROM` lines track the engine-qualified base.** Change `Dockerfile.custom:1`, `Dockerfile.pywal:1`, `Dockerfile.wallust:1` from `FROM color-scheme-base:latest` to `ARG BASE_IMAGE=csg-color-scheme-base-docker:latest` + `FROM ${BASE_IMAGE}`. The default arg keeps standalone `docker build` working; `install_cmd.py` passes `BuildContext(build_args={"BASE_IMAGE": <csg-color-scheme-base-{engine}:{tag}>})` so the backend build resolves the same base install just produced. `Dockerfile.base` (FROM `python:3.14-slim`) is unchanged. `BuildContext.build_args` is already emitted as `--build-arg` by `oci_runtime/adapters/managers/image.py`.

5. **Engine resolution is the same everywhere:** `--container-engine` override → `settings.container.engine` → `DOCKER`. The qualifier is always applied, default included, for one consistent code path.

6. **Tests assert the built/removed/resolved tag strings** for both engines (not just build counts) and cover the docker default. Stale mocks/scripts referencing obsolete names are updated.

**Non-goals:**

- Adding an `image_registry` field to CSG `ContainerSettings` (designed in the plan but never implemented — stays out of scope).
- Fixing WEG `tests/unit/adapters/test_docker_image_manager.py`, which imports a deleted module — pre-existing breakage unrelated to engine tagging.
- Changing `--container-engine` scoping (already settled by the `cli-flag-scope-refinement` change).
- Persisting the engine-qualified name in TOML — config stores the *base* name/tag; the qualifier is derived at use time.

## Capabilities

### New Capabilities
- `container-image-engine-tagging`: A shared `oci-runtime` helper produces engine-qualified image names of the form `{registry/}{name}-{engine}:{tag}`, always applied (docker included), so podman- and docker-built images never collide. WEG and CSG construct all build/uninstall/run image references through it.

### Modified Capabilities
- `csg-image-naming`: Normalized to a hyphenated `csg-color-scheme-{segment}` scheme applied uniformly to base and backend images, retiring the no-separator `csgcolor-scheme-*` concatenation and the prefixless `color-scheme-base` literal. Backend Dockerfiles reference the base via `ARG BASE_IMAGE` so the FROM line tracks the engine-qualified base tag without manual edits.

## Impact

- **Shared layer (2 files + tests):** new `oci_runtime/domain/naming.py`, export added to `oci_runtime/__init__.py`, new unit tests under `src/shared/oci-runtime/tests/`.
- **WEG (3 files + tests):** `cli/install.py`, `cli/uninstall.py`, `adapters/container_processor.py`. Tests in `tests/test_cli.py` (install/uninstall assertions) — `ghcr.io/weg-managed:latest` mocks become `ghcr.io/weg-managed-docker:latest` / `-podman`.
- **CSG (7 files + tests):** `cli/_helpers.py`, `cli/install_cmd.py`, `cli/uninstall_cmd.py`, `adapters/container_processor.py`, `adapters/dry_run_processor.py`, `Dockerfile.custom`, `Dockerfile.pywal`, `Dockerfile.wallust`. Tests in `tests/unit/cli/test_install_command.py`, `tests/unit/cli/test_uninstall_command.py`, `tests/unit/adapters/test_image_lifecycle.py`.
- **User-visible:** `weg install --container-engine podman` now yields `weg-podman:latest`; `csg install --container-engine podman` now yields `csg-color-scheme-base-podman:latest` and `csg-color-scheme-{custom,pywal,wallust}-podman:latest`. Both engine variants can coexist in the same image store.
- **Migration:** pre-existing engine-less images (`weg:latest`, `color-scheme-base:latest`, `csgcolor-scheme-*:latest`) are not auto-removed. Users running both engines should `uninstall` the old names or accept that they become orphaned (harmless). Documented in the change's design.