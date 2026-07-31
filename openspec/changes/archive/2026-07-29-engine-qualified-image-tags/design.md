## Context

WEG (`weg`) and CSG (`csg`) are sibling CLI tools that build OCI container images from bundled Dockerfiles and later run those images. Investigation confirmed:

- **The engine choice reaches the build only as the binary selector**, never as part of the image identity. `--container-engine podman` picks the `podman` binary; the tag passed to `-t` is constructed from `image_name`/`image_prefix` + `image_tag` and is identical for docker and podman. Both engines' images land under the same repository:tag.
- **WEG duplicates the tag builder in three places** that must stay in lockstep or the run path fails to find what install built: `cli/install.py:72-79` `_build_image_name`, `cli/uninstall.py:51-58` `_build_image_name`, `adapters/container_processor.py:250-257` `_resolve_image`. Each independently assembles `f"{name}:{tag}"` / `f"{registry}/{name}:{tag}"`.
- **CSG duplicates the builder in three places too:** `cli/_helpers.py:124-126` `build_image_name` (used by both install and uninstall), `adapters/container_processor.py:55-58` `_select_image`, `adapters/dry_run_processor.py:50-52` `_build_image_name`. The base image is a *separate hardcoded literal* `"color-scheme-base:latest"` at `install_cmd.py:57` that bypasses the helper entirely.
- **CSG naming is internally inconsistent.** Backend images use `image_prefix` ("csg") concatenated with the literal `"color-scheme-"` segment with no separator ⇒ `csgcolor-scheme-custom:latest`. The base image carries no prefix at all ⇒ `color-scheme-base:latest`. The architecture plan documented `csg-color-scheme-*` and `color-scheme-*`; tests reference `csg-color-scheme-custom`. Three different spellings across code, plan, and tests.
- **CSG backend Dockerfiles hardcode `FROM color-scheme-base:latest`.** Re-tagging the base naively breaks the backend builds because the FROM line won't resolve.
- **The shared `oci-runtime` layer already supports `--build-arg`** via `BuildContext.build_args` (emitted at `adapters/managers/image.py:73-74`) and `build_file_path`/`context_path`. It treats the image name as an opaque string passed to `-t`. Engine-qualification belongs in the tool layer, with the actual build plumbing already sufficient.

## Goals / Non-Goals

**Goals:**
- A user can tell at a glance whether an image in `docker images` / `podman images` was built for that engine.
- Both engine variants can coexist in the same image store without one shadowing the other.
- One shared, tested function produces every image reference; install, uninstall, and run paths cannot drift.
- CSG base and backend images follow a single consistent, hyphenated naming scheme.
- Changing the base tag automatically reaches the backend Dockerfiles without manual edits.

**Non-Goals:**
- Backfilling CSG's designed-but-unimplemented `image_registry` field.
- Auto-cleaning pre-existing engine-less images from users' image stores.
- Touching `--container-engine` flag scoping (settled by `cli-flag-scope-refinement`).
- Persisting the engine-qualified name in config — the base name/tag are stored; the qualifier is derived.

## Decisions

### D1: Engine goes in the *name*, not the tag

**Choice:** Image identity is `{name}-{engine}:{tag}` — e.g. `weg-podman:latest`, `csg-color-scheme-base-podman:latest`. The engine-agnostic `image_tag` setting (default `"latest"`) remains the configurable tag, untouched.

**Alternatives considered:**
- *Suffix the tag (`weg:latest-podman`):* Keeps the repository clean. Rejected because the tag is a user-facing config setting; folding an engine string into it means the persisted `image_tag` would not match the actual tag, creating a confusing config-vs-reality mismatch.
- *Engine as the tag (`weg:podman`):* Drops the configurable tag entirely, removing user control over version pinning.
- *Conditional suffix (only when non-default):* Two code paths; "is the default docker?" becomes an implicit rule the user must know. Always-suffix gives one uniform rule and unambiguous images.

**Why this choice:** The repository/name is the natural identity slot for "thing built for X"; the tag remains free for versioning. Always-suffix (docker included) yields one code path and makes the docker variant explicit rather than implicit. Per the user's steering decision.

### D2: Single shared helper in `oci-runtime`

**Choice:** Add `oci_runtime.domain.naming.engine_qualified_image(name, engine, tag, registry=None) -> str`:

```python
def engine_qualified_image(name: str, engine: str, tag: str, registry: str | None = None) -> str:
    if not engine:
        raise ValueError("engine is required for an engine-qualified image name")
    repo = f"{name}-{engine}"
    image = f"{repo}:{tag}"
    if registry:
        return f"{registry.rstrip('/')}/{image}"
    return image
```

Export from `oci_runtime/__init__.py` (add to `__all__`). Every WEG/CSG construction site calls it instead of inlining `f"{...}:{tag}"`. The `engine` argument is the lowercase string value (`"docker"` / `"podman"`), obtained from the resolved `ContainerEngine` enum.

**Alternatives considered:**
- *Per-tool helper, duplicated:* Reject — the whole point is eliminating the three-times-duplicated assembly.
- *Add the helper to each tool's own `_helpers.py`:* Duplicates the rule across WEG and CSG; `oci-runtime` is already the shared layer both tools depend on, so it is the correct home.

**Why this choice:** `oci-runtime` already owns the build/run plumbing and is imported by both tools. One tested function, one rule, no drift.

### D3: WEG wires the helper into all three sites without changing defaults

**Choice:** Replace the body of each WEG `_build_image_name` / `_resolve_image` with a call to `engine_qualified_image(cs.image_name, cs.engine, cs.image_tag, cs.image_registry)`. `ContainerSettings` (`domain/models.py:152-157`), `ContainerSettingsSchema` (`adapters/schemas/settings_schema.py:29-33`), and `defaults/settings.toml` keep `image_name="weg"`, `image_tag="latest"` — the qualifier is *computed* from `cs.engine`, never persisted.

**Resulting names:** `weg-docker:latest`, `weg-podman:latest`, `ghcr.io/weg-managed-podman:latest` (when `image_registry="ghcr.io"` + `image_name="weg-managed"`).

**Why no signature changes are needed:** All three sites already receive the full `ContainerSettings` (install/uninstall via `settings.container`; runtime via `self._container_settings`). The `engine` field is already populated by the existing override plumbing (`cli/install.py:30-45`, `cli/process.py:69-71`). No new parameter, no new override rule — just swap the assembly line.

### D4: CSG normalizes naming and uses the helper

**Choice:** CSG moves to a single hyphenated scheme `{prefix}-color-scheme-{segment}` applied to both base and backends. `build_image_name(settings, backend, engine)` becomes:

```python
def build_image_name(settings: AppSettings, backend: Backend, engine: str) -> str:
    base = f"{settings.container.image_prefix}-color-scheme-{backend.image_suffix}"
    return engine_qualified_image(base, engine, settings.container.image_tag)
```

The base literal in `install_cmd.py:57` becomes `engine_qualified_image(f"{settings.container.image_prefix}-color-scheme-base", engine_value, settings.container.image_tag)`. With default `image_prefix="csg"`, `image_tag="latest"`:
- Base: `csg-color-scheme-base-podman:latest`
- Custom: `csg-color-scheme-custom-podman:latest`
- Pywal: `csg-color-scheme-pywal-podman:latest`
- Wallust: `csg-color-scheme-wallust-podman:latest`

**Why normalize now:** The pre-existing inconsistency (`csgcolor-scheme-*` concatenation, prefixless `color-scheme-base`, mismatches in plan and tests) is a real bug. The engine-tagging change is already touching every naming site, so carrying the normalization in the same change is cheaper than a separate one and avoids two rounds of test churn. Per the user's steering decision.

**Threading `engine` through:** `install_cmd.py` resolves `engine = container_engine or ContainerEngine(settings.container.engine) or ContainerEngine.DOCKER` **before** the local `container_engine` variable is reassigned to the runtime object at line 52. Capture `engine_value = engine.value` and pass it to `build_image_name` (line 78) and the base construction (line 57). `uninstall_cmd.py` resolves the same way and passes `engine_value` to the same helper (it already calls `build_image_name`, just with a new positional arg). The runtime path (`main.py` generate body, ~lines 247-249) already resolves an `engine_obj` — pass its `.value` into the processor construction so `_select_image` can qualify identically.

### D5: CSG backend Dockerfiles use `ARG BASE_IMAGE`

**Choice:** Replace `FROM color-scheme-base:latest` in `Dockerfile.custom:1`, `Dockerfile.pywal:1`, `Dockerfile.wallust:1` with:

```dockerfile
ARG BASE_IMAGE=csg-color-scheme-base-docker:latest
FROM ${BASE_IMAGE}
```

`install_cmd.py` builds the backend `BuildContext` with `build_args={"BASE_IMAGE": base_image}` where `base_image` is the same engine-qualified base name just built. `BuildContext.build_args` is already emitted as `--build-arg BASE_IMAGE=...` by `oci_runtime/adapters/managers/image.py:73-74`. No shared-layer change needed for the build-arg path.

**Why the `ARG` default is the docker variant:** Standalone `docker build -f Dockerfile.custom .` (no `--build-arg`) still resolves a valid base image. In the install flow, `--build-arg BASE_IMAGE` overrides it with the engine-qualified name. This keeps the Dockerfiles usable outside the install path.

**Why not parametrize the whole name in the Dockerfile:** Build args are the minimal, idiomatic mechanism. The base name is produced in Python next to where the base is built, so the single source of truth stays in `install_cmd.py` + the helper.

### D6: Engine resolution order is identical everywhere

**Choice:** `engine = <CLI override> or settings.container.engine or DOCKER` (CSG, matching WEG's existing pattern). The qualifier is applied in *every* construction path — install, uninstall, runtime run, dry-run — using the same resolved value. There is no "skip qualifier for docker" branch; docker yields `-docker` like podman yields `-podman`.

**Rationale:** One rule, testable with a single parameter sweep over the two enum values. A user who builds for docker and later for podman sees both images coexist (`weg-docker:latest`, `weg-podman:latest`). The "always applied" decision was the user's steering choice.

## Risks / Trade-offs

- **[Migration: dangling images]** Existing `weg:latest`, `color-scheme-base:latest`, `csgcolor-scheme-*:latest` images remain in users' stores after the upgrade; the new names do not overwrite them. **Mitigation:** Harmless (just disk space). Document in the change notes that a one-time `docker rmi`/`podman rmi` of the old names reclaims space. No automated cleanup is shipped — auto-removing images is risky and out of scope.
- **[Default-arg assumes docker]** `ARG BASE_IMAGE=csg-color-scheme-base-docker:latest` means a podman-only user running a backend Dockerfile manually without `--build-arg` would try to resolve the docker base. **Mitigation:** The install flow always supplies `--build-arg`; standalone manual builds are a developer convenience, and a podman user building standalone would also need a docker base present, which is the documented default-engine behavior. Acceptable.
- **[Test mock churn]** Several tests reference the old names as exception arguments or mock return values (`csg-color-scheme-custom:latest`, `ghcr.io/weg-managed:latest`). **Mitigation:** Update test literals in the same change; these are not behavioral assertions, just fixture strings, so the updates are mechanical.
- **[Breaking change for scripts pinning old names]** Any external automation that hardcodes `weg:latest` to run the image breaks. **Mitigation:** Both tools are internal to this repo; the only consumers are these tools' own run/tests, which move to the new names in the same change. Documented as a breaking change in the proposal.
- **[Dockerfile FROM default mismatch with `--build-arg` from a *different* engine]** If a user runs `csg install --container-engine podman`, install builds `csg-color-scheme-base-podman:latest`, then passes `BASE_IMAGE=csg-color-scheme-base-podman:latest` to the backend builds — consistent. The default arg is only used on standalone builds, which default to docker. No mismatch within the install flow.