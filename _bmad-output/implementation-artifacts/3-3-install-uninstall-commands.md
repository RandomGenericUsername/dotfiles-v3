---
baseline_commit: 26fde9e23b524fb17daedaed54a158552a875519
---

# Story 3.3: Install/Uninstall Commands

Status: done

## Story

As a theming user,
I want to build and remove per-backend container images,
so that I can use container-mode execution.

## Acceptance Criteria

### AC 1: Install builds all backend images
**Given** the install command
**When** `csg install` is run
**Then** it builds all three backend images via `engine.images.build()`
**And** uses per-backend Dockerfiles from `adapters/docker/` based on Dockerfile.base (python:3.14-slim)

### AC 2: Install with --backend filter
**Given** `csg install --backend custom` is run
**Then** only custom image is built
**And** image is named `[registry/]color-scheme-custom:<tag>`
**And** supports `--engine docker|podman` and `--dry-run`

### AC 3: Dockerfile discovery
**Given** Dockerfile discovery via `importlib.resources`
**When** running in editable dev install
**Then** Dockerfiles are found correctly (tested for both editable and installed modes)

### AC 4: Uninstall removes images with confirmation
**Given** the uninstall command
**When** `csg uninstall` is run
**Then** it removes all backend images (with confirmation prompt)

### AC 5: Uninstall with --backend and auto-confirm
**Given** `csg uninstall --backend wallust --yes` is run
**Then** removes only wallust image without prompting

### AC 6: Image lifecycle error mapping
**Given** image lifecycle errors
**When** `engine.images.build()` fails
**Then** error maps to a domain exception with diagnostic message
**When** `engine.images.remove()` fails
**Then** error maps similarly

## Tasks / Subtasks

### Extend ContainerRuntimePort with build/remove methods
- [x] Add `build_image(context: BuildContext, image_name: str, timeout: int | None = 600) -> str` to port (AC: 1)
- [x] Add `remove_image(image: str, force: bool = False) -> None` to port (AC: 4)
- [x] Both return types are from oci-runtime; port stays abstract — adapter owns mapping

### Implement build_image / remove_image in OciContainerRuntimeAdapter
- [x] Delegate `build_image` to `self._engine.images.build(context, image_name, timeout)` (AC: 1)
- [x] Delegate `remove_image` to `self._engine.images.remove(image, force)` (AC: 4)
- [x] Catch oci-runtime exceptions and re-raise as domain exceptions (AC: 6)

### Add domain exceptions for image lifecycle errors
- [x] `ImageBuildError(image, reason, backend=None)` (AC: 6)
- [x] `ImageRemoveError(image, reason, backend=None)` (AC: 6)
- [x] Both inherit from `ColorSchemeError`

### Create per-backend Dockerfiles as package data
- [x] Create `adapters/docker/Dockerfile.base` — FROM python:3.14-slim, csg installed via pip (AC: 1)
- [x] Create `adapters/docker/Dockerfile.custom` — FROM Dockerfile.base, install custom deps (pillow, numpy, scikit-learn)
- [x] Create `adapters/docker/Dockerfile.pywal` — FROM Dockerfile.base, install pywal
- [x] Create `adapters/docker/Dockerfile.wallust` — FROM Dockerfile.base, install wallust binary
- [x] Add `adapters/docker/__init__.py` (empty)
- [x] Update `pyproject.toml` to include Dockerfiles as package data (AC: 3)

### Create install_cmd.py
- [x] Define `install` function: `(ctx: typer.Context, backend: list[Backend], engine: ContainerEngine, dry_run: bool)` (AC: 1, 2)
- [x] Resolve `AppSettings` via `deps.config_resolver` (AC: 2, image naming)
- [x] Determine target backends: all three if `--backend` omitted, filtered otherwise (AC: 2)
- [x] For each target backend:
  - [x] Construct image name from container settings
  - [x] Resolve Dockerfile via `importlib.resources.files()`
  - [x] Build `BuildContext(build_file_path=dockerfile_path)` (AC: 1)
  - [x] If `--dry-run`: log what would be built without executing (AC: 2)
  - [x] Call `deps.container_engine.build_image(context, image_name)` (AC: 1)
- [x] Catch `ColorSchemeError` → `deps.output_adapter.error(exc)` + `typer.Exit(code=1)`
- [x] Format output per output adapter (AC: 2)

### Create uninstall_cmd.py
- [x] Define `uninstall` function: `(ctx: typer.Context, backend: list[Backend], yes: bool, engine: ContainerEngine, dry_run: bool)` (AC: 4, 5)
- [x] Resolve `AppSettings` (AC: 4, image naming)
- [x] Determine target backends (AC: 5)
- [x] If not `--yes` and no `--backend` filter: prompt confirmation (AC: 4)
- [x] For each target backend:
  - [x] Construct image name
  - [x] If `--dry-run`: log what would be removed
  - [x] Call `deps.container_engine.remove_image(image_name)` (AC: 4)
- [x] Catch `ColorSchemeError` → `deps.output_adapter.error(exc)` + `typer.Exit(code=1)`

### Register commands in main.py
- [x] Import `install` from `cli.install_cmd` (AC: 1)
- [x] Import `uninstall` from `cli.uninstall_cmd` (AC: 4)
- [x] Add `app.command()(install)` and `app.command()(uninstall)`
- [x] Lazy container engine init in install/uninstall commands (not in callback)

### Update factory.py if needed
- [x] Check if `CliDependencies` or factory functions need updates for install/uninstall wiring
- [x] Install/uninstall only need `container_engine` and `config_resolver` — both already in `CliDependencies`

### Write tests
- [x] CLI test: `csg install` builds all three images (mock `container_engine.build_image`) (AC: 1)
- [x] CLI test: `csg install --backend custom` builds only custom (AC: 2)
- [x] CLI test: `csg install --dry-run` logs plan without building (AC: 2)
- [x] CLI test: `csg install --engine podman` selects Podman engine (AC: 2)
- [x] CLI test: `csg install` build failure → error output (AC: 6)
- [x] CLI test: `csg uninstall` with --yes removes all images (AC: 4)
- [x] CLI test: `csg uninstall --yes` skips prompt (AC: 5)
- [x] CLI test: `csg uninstall --backend wallust` removes only wallust (AC: 5)
- [x] CLI test: `csg uninstall --dry-run` logs plan without removing (AC: 4)
- [x] CLI test: `csg uninstall` removal failure → error output (AC: 6)
- [x] CLI test: help text for both commands
- [x] Unit test: `build_image` delegates to oci-runtime engine.images.build() (AC: 1)
- [x] Unit test: `remove_image` delegates to oci-runtime engine.images.remove() (AC: 4)
- [x] Unit test: oci-runtime build error maps to `ImageBuildError` (AC: 6)
- [x] Unit test: oci-runtime remove error maps to `ImageRemoveError` (AC: 6)
- [x] Unit test: Dockerfile resolution via importlib.resources works in both editable and installed modes (AC: 3)
- [x] Run full test suite — 382 passed, zero regressions
- [x] Run ruff lint — clean (new code)

## Dev Notes

### Current State

**`ports/container_runtime.py`** — only has `run`, `image_exists`, `pull_image`. No build/remove:
```python
@runtime_checkable
class ContainerRuntimePort(Protocol):
    def run(self, image, command, mounts, timeout) -> ContainerResult: ...
    def image_exists(self, image) -> bool: ...
    def pull_image(self, image) -> None: ...
```

**`adapters/oci_container_runtime.py`** — wraps `oci_runtime.ports.engine.ContainerEngine`:
- `run()` → `engine.containers.run()` + `engine.containers.exec_container()`
- `image_exists()` → `engine.images.exists()`
- `pull_image()` → `engine.images.pull()`
- No build/remove forwarding yet

**`oci_runtime` API** (already available via `engine.images`):
- `engine.images.build(context: BuildContext, image_name: str, timeout: float | None = 600.0) -> str`
- `engine.images.remove(image: str, force: bool = False) -> None`
- `BuildContext` (frozen dataclass): `build_file_content | build_file_path`, `context_path`, `files`, `build_args`, `no_cache`, `pull`, `rm`, etc.

**No Dockerfiles exist** — must be created as package data under `adapters/docker/`:
- `Dockerfile.base` — shared python:3.14-slim base
- `Dockerfile.custom` — extends base with pillow + numpy + scikit-learn
- `Dockerfile.pywal` — extends base with pywal pip install
- `Dockerfile.wallust` — extends base with wallust binary install

**`domain/exceptions.py`** — has container exceptions (`ContainerImageNotFoundError`, `ContainerRuntimeUnavailableError`, `ContainerTimeoutError`, `ImagePullAccessError`). Missing `ImageBuildError` and `ImageRemoveError`.

**`factory.py`** — `CliDependencies` has `container_engine: ContainerRuntimePort | None`. Install/uninstall need it populated even in `--runtime local` mode. Currently only created for container mode in the callback.

**`cli/main.py`** — commands are registered via `app.command()(func)` pattern. `generate` is inline; others imported.

**`domain/models.py`** — `ContainerSettings(image_prefix, image_tag, timeout_seconds, memory_limit, mount_timeout_seconds)` — image naming uses `image_prefix` + `color-scheme-<suffix>` + `:image_tag`.

**`domain/enums.py`** — `Backend` has `image_suffix` property returning `self.value` (custom/pywal/wallust).

### Implementation Strategy

**ContainerRuntimePort extension:**
```python
def build_image(self, context: BuildContext, image_name: str, timeout: int | None = 600) -> str: ...
def remove_image(self, image: str, force: bool = False) -> None: ...
```
`BuildContext` is from oci-runtime. Import under `TYPE_CHECKING` to avoid runtime dep.

**OciContainerRuntimeAdapter implementation:**
```python
def build_image(self, context, image_name, timeout=600):
    from oci_runtime.domain.exceptions import ImageError
    try:
        return self._engine.images.build(context, image_name, timeout)
    except ImageError as exc:
        raise ImageBuildError(backend=..., image=image_name, reason=str(exc)) from exc

def remove_image(self, image, force=False):
    from oci_runtime.domain.exceptions import ImageError
    try:
        self._engine.images.remove(image, force=force)
    except ImageError as exc:
        raise ImageRemoveError(image=image, reason=str(exc)) from exc
```
Backend must be determined in the caller (install_cmd) and passed through — adapter only knows image name.

Alternative: pass backend to adapter methods. Better: let the CLI command handle backend mapping and pass backend to the exception construction in the adapter. Or use container settings to derive backend.

**Image naming:**
```
image_name = f"{container_settings.image_prefix}color-scheme-{backend.image_suffix}:{container_settings.image_tag}"
```

**Dockerfile layout:**
```
adapters/docker/
  __init__.py
  Dockerfile.base
  Dockerfile.custom
  Dockerfile.pywal
  Dockerfile.wallust
```

**Dockerfile.base content:**
```dockerfile
FROM python:3.14-slim
RUN pip install --no-cache-dir color-scheme-generator
```

**Dockerfile.custom:**
```dockerfile
FROM color-scheme-base:latest
RUN pip install --no-cache-dir pillow numpy scikit-learn
```
Or combine as a multi-stage. The exact Dockerfile content needs investigation — aim is to produce a minimal image with csg + backend deps.

**Dockerfile discovery:**
```python
from importlib.resources import files as pkg_files
dockerfile_path = pkg_files("color_scheme_generator.adapters.docker").joinpath(f"Dockerfile.{backend.image_suffix}")
```
This works in both editable and installed modes when Dockerfiles are included as package data.

**Install command outline:**
```python
def install(
    ctx: typer.Context,
    backend: list[Backend] = typer.Option([], "--backend", help="Backends to build"),
    engine: ContainerEngine = typer.Option(ContainerEngine.DOCKER, "--engine", help="Container engine"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without building"),
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    try:
        settings = deps.config_resolver.resolve()
        container_engine = _get_container_engine(deps, engine)
        target_backends = backend or list(Backend)
        for b in target_backends:
            image = _build_image_name(settings, b)
            if dry_run:
                ...  # log plan
            else:
                dockerfile = _resolve_dockerfile(b)
                context = BuildContext(build_file_path=dockerfile)
                container_engine.build_image(context, image)
        ...
```

**Uninstall command outline:**
```python
def uninstall(
    ctx: typer.Context,
    backend: list[Backend] = typer.Option([], "--backend", help="Backends to remove"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    engine: ContainerEngine = typer.Option(ContainerEngine.DOCKER, "--engine", help="Container engine"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without removing"),
) -> None:
    deps: CliDependencies = ctx.obj["deps"]
    try:
        settings = deps.config_resolver.resolve()
        container_engine = _get_container_engine(deps, engine)
        target_backends = backend or list(Backend)
        if not yes and not backend:
            typer.confirm(f"Remove {len(target_backends)} backend images?", abort=True)
        for b in target_backends:
            image = _build_image_name(settings, b)
            if dry_run:
                ...  # log plan
            else:
                container_engine.remove_image(image)
        ...
```

**Container engine lazy initialization:**
Install/uninstall need `container_engine` even in local mode. The callback currently only creates it for `--runtime container`. Two options:
1. Move `create_container_engine` call into install/uninstall commands (lazy)
2. Always create container_engine in callback (default engine)

Option 1 is cleaner — avoids unnecessary engine creation when running local-only commands.

### Previous Story Intelligence (3.2)

- `ContainerProcessor` serializes AppSettings to temp TOML via manual TOML construction (tomli_w not available)
- Inner command: `csg generate /input/img --runtime local --backend <backend> --param ...`
- 4 BIND mounts: input (RO), output (RW), settings (RO), templates (RO)
- Root FS guard: raise `InvalidImageError` if `image_path.parent == Path("/")`
- Temp file: `NamedTemporaryFile(delete=False, suffix=".toml", mode="w")`, `os.chmod(path, 0o644)`, cleanup in finally
- Test patterns: mock `ContainerRuntimePort`, `tmp_path` for temp files, verify result field-by-field
- 363 tests passing, ruff clean
- Key: `OciContainerRuntimeAdapter` wraps `oci_runtime` engine — `engine.images` already exposes `build()` and `remove()`

### Architecture Compliance

- **ADR-005 (One Image Per Backend):** Image tag is `color-scheme-<backend>:<tag>` — matches per-backend Dockerfiles from Dockerfile.base
- **ADR-008 (Ephemeral In-Container Cache):** Images are built for container-mode extraction; no host cache mount needed
- **ADR-014 (Shared Dockerfile.base):** One image per backend built on shared base. Dockerfile layout matches this convention
- **JSON-First Output:** Install/uninstall results render through `deps.output_adapter` — follows all existing command patterns
- **Error Contract:** All errors produce structured output via `deps.output_adapter.error(exc)` — follows NFR-2

### Testing Patterns

Follow existing patterns from:
- `tests/unit/cli/test_list_backends_command.py` — mock deps, CliRunner, monkeypatch `build_deps`
- `tests/unit/cli/test_runtime_mode.py` — test `--engine` flag dispatch
- `tests/unit/adapters/test_container_processor.py` — mock ContainerRuntimePort, tmp_path

CLI tests:
- `monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)`
- Use `CliRunner().invoke(app, ["install", "--backend", "custom", "--dry-run"])`
- Verify exit code, mock calls, stdout content

Adapter tests:
- Directly instantiate `OciContainerRuntimeAdapter` with mock `engine`
- Verify delegation to `engine.images.build()` / `engine.images.remove()`
- Verify error mapping from oci-runtime exceptions → domain exceptions

### Files to Create

| File | Action |
|------|--------|
| `src/color_scheme_generator/cli/install_cmd.py` | CREATE — install command |
| `src/color_scheme_generator/cli/uninstall_cmd.py` | CREATE — uninstall command |
| `src/color_scheme_generator/adapters/docker/__init__.py` | CREATE — package marker |
| `src/color_scheme_generator/adapters/docker/Dockerfile.base` | CREATE — shared base image |
| `src/color_scheme_generator/adapters/docker/Dockerfile.custom` | CREATE — custom backend image |
| `src/color_scheme_generator/adapters/docker/Dockerfile.pywal` | CREATE — pywal backend image |
| `src/color_scheme_generator/adapters/docker/Dockerfile.wallust` | CREATE — wallust backend image |
| `tests/unit/cli/test_install_command.py` | CREATE — install CLI tests |
| `tests/unit/cli/test_uninstall_command.py` | CREATE — uninstall CLI tests |

### Files to Modify

| File | Action |
|------|--------|
| `src/color_scheme_generator/ports/container_runtime.py` | MODIFY — add `build_image`, `remove_image` |
| `src/color_scheme_generator/adapters/oci_container_runtime.py` | MODIFY — implement `build_image`, `remove_image` with error mapping |
| `src/color_scheme_generator/cli/main.py` | MODIFY — register install/uninstall commands |
| `src/color_scheme_generator/domain/exceptions.py` | MODIFY — add `ImageBuildError`, `ImageRemoveError` |
| `pyproject.toml` | MODIFY — include Dockerfiles as package data |

### References

- [Source: epics.md#650-681] — Story 3.3 acceptance criteria
- [Source: epics.md#82-83] — FR-6 install, FR-7 uninstall
- [Source: prd.md#122-147] — FR-6 and FR-7 detailed consequences
- [Source: ports/container_runtime.py:1-23] — Current port (needs build/remove)
- [Source: adapters/oci_container_runtime.py:1-61] — Current adapter (needs build/remove forwarding)
- [Source: factory.py:85-101] — create_container_engine pattern
- [Source: cli/main.py:154-159] — Command registration pattern
- [Source: domain/exceptions.py:82-103] — Existing container exceptions
- [Source: domain/models.py:130-135] — ContainerSettings with image_prefix, image_tag
- [Source: domain/enums.py:20-22] — Backend.image_suffix property
- [Source: oci-runtime ports/managers.py] — ImageManager.build(), ImageManager.remove()
- [Source: oci-runtime domain/types.py] — BuildContext dataclass
- [Source: oci-runtime domain/exceptions.py] — ImageError base exception

### Project Structure Notes

- Install/uninstall commands live in `cli/` as standalone modules, following `info_cmd.py`, `list_backends_cmd.py` pattern
- Dockerfiles live under `adapters/docker/` as package data, discovered via `importlib.resources`
- `ContainerRuntimePort` extension is a non-breaking additive change — existing methods unchanged
- Image naming convention matches what `ContainerProcessor` uses: `{prefix}color-scheme-{suffix}:{tag}`
- `_get_container_engine()` helper can be shared via `_helpers.py` or inlined in each command
- Container engine created lazily in install/uninstall (not in callback) since these are the only commands that build/remove images

### Deferred / Investigate

1. **Dockerfile.base strategy** — whether to build as standalone image or use multi-stage. Investigate minimal size approach: base with csg installed, per-backend images install additional deps on top.
2. **importlib.resources vs pkg_resources** — use `importlib.resources.files()` (Python 3.14). Verify works in both editable (pip install -e) and installed modes.
3. **Backend extraction for error mapping** — `oci_container_runtime.build_image()` doesn't know which backend is being built. Pass backend as a parameter or extract from image name convention.
4. **Image existence at uninstall** — should uninstall fail if image doesn't exist? Probably continue silently with a warning.
5. **--dump-config and --dump-templates post-install bootstrap** — PRD mentions these as install command features. Evaluate if in scope or defer.

### Review Findings

- [x] [Review][Decision] Base image build ordering — Build base first in install loop before per-backend images. [Dockerfile.base, Dockerfile.custom:1, install_cmd.py]
- [x] [Review][Decision] Dockerfile.wallust installation method — Use pre-built binary download from Codeberg releases (`wallust-x86_64-unknown-linux-musl.tar.gz`) instead of apt-get. [Dockerfile.wallust:2]
- [x] [Review][Patch] Uninstall confirmation bypass [uninstall_cmd.py:45] — `if not yes and not backend:` skips confirmation when `--backend` is specified without `--yes`. Fix: change to `if not yes:`.
- [x] [Review][Patch] Broaden exception handling [install_cmd.py:92, uninstall_cmd.py:85] — Only catches `ColorSchemeError`. Non-domain exceptions (OSError, PermissionError) crash. Fix: add `except Exception` like `generate` command does.
- [x] [Review][Patch] Dockerfile existence not validated [install_cmd.py:65-66] — `_resolve_dockerfile` returns a path but `BuildContext` will fail with uncatchable error if file missing. Fix: validate with `Path.exists()`.
- [x] [Review][Patch] No --force flag for uninstall [uninstall_cmd.py:60] — `remove_image` always called with `force=False`. Running containers block removal. Fix: add `--force` CLI option.
- [x] [Review][Patch] backend not passed to exception constructors [install_cmd.py:67, oci_container_runtime.py:77-79] — `ImageBuildError`/`ImageRemoveError` always receive `backend=None`. Fix: pass backend from CLI loop through adapter.
- [x] [Review][Patch] Timeout value not validated [oci_container_runtime.py:68] — `timeout: int | None = 600` accepts 0, -1, None. Fix: validate timeout > 0.
- [x] [Review][Patch] Empty image_name/reason not validated [domain/exceptions.py:106-125] — Exception constructors accept empty strings. Fix: validate non-empty.
- [x] [Review][Patch] Duplicate backends cause redundant work [install_cmd.py:54] — `--backend base --backend base` builds/removes image twice. Fix: deduplicate backend list.
- [x] [Review][Patch] _build_image_name duplicated [install_cmd.py:27-29, uninstall_cmd.py:26-28] — Identical function in two modules. Fix: extract to shared helper.
- [x] [Review][Patch] _get_container_engine unused deps parameter [install_cmd.py:20-24, uninstall_cmd.py:19-23] — Takes `deps` but ignores it. Fix: remove parameter.
- [x] [Review][Patch] Fragile timeout test [test_image_lifecycle.py:71-83] — Uses manual call-arg indexing. Fix: use `.call_args.kwargs.get("timeout")`.
- [x] [Review][Patch] Unused fixture parameter [test_install_command.py:53, test_uninstall_command.py:53] — `mock_deps` declares `mock_container_engine` but never uses it. Fix: remove param.
- [x] [Review][Patch] Private _console access [install_cmd.py:86-88, uninstall_cmd.py:79-81] — `adapter._console.print()` accesses private attribute. Fix: add public `print_table` method to `RichOutput`.
- [x] [Review][Defer] Partial failure orphans images [install_cmd.py, uninstall_cmd.py] — deferred, pre-existing — no rollback for partially built/removed images; inherent to sequential CLI pattern
- [x] [Review][Defer] Unknown output adapter silent [install_cmd.py:74-91, uninstall_cmd.py:67-84] — deferred, pre-existing — future adapter types silently discard results
- [x] [Review][Defer] Non-ImageError engine exceptions unhandled [oci_container_runtime.py:74-76, 87-89] — deferred, pre-existing — requires oci-runtime exception knowledge
- [x] [Review][Defer] No .dockerignore [Dockerfiles] — deferred, pre-existing — builds include unnecessary context
- [x] [Review][Defer] No --image-tag CLI flag [install_cmd.py, uninstall_cmd.py] — deferred, pre-existing — feature request, tag always from config
- [x] [Review][Defer] No CLI integration tests — deferred, pre-existing — tests use unit mocking pattern
- [x] [Review][Defer] build_image return value discarded [install_cmd.py:67] — deferred, pre-existing — image SHA not captured/displayed

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

### Completion Notes List

- Implemented `build_image` and `remove_image` on `ContainerRuntimePort` protocol
- Added `ImageBuildError` and `ImageRemoveError` domain exceptions (backend optional)
- Implemented `build_image`/`remove_image` in `OciContainerRuntimeAdapter` with oci-runtime `ImageError` mapping
- Created 4 Dockerfiles under `adapters/docker/` (base, custom, pywal, wallust)
- Created `install_cmd.py` with `--backend`, `--engine`, `--dry-run` options and multi-format output
- Created `uninstall_cmd.py` with `--backend`, `--yes`, `--dry-run` options and confirmation prompt
- Registered install/uninstall commands in `main.py` with lazy container engine initialization
- Added 19 new tests: 6 install CLI, 6 uninstall CLI, 7 adapter/unit tests
- All 382 tests pass, ruff lint clean for new code

### File List

| File | Action |
|------|--------|
| `src/color_scheme_generator/ports/container_runtime.py` | MODIFIED — added `build_image`, `remove_image` |
| `src/color_scheme_generator/adapters/oci_container_runtime.py` | MODIFIED — implemented `build_image`, `remove_image` with error mapping |
| `src/color_scheme_generator/domain/exceptions.py` | MODIFIED — added `ImageBuildError`, `ImageRemoveError` |
| `src/color_scheme_generator/cli/main.py` | MODIFIED — registered install/uninstall commands |
| `pyproject.toml` | MODIFIED — include Dockerfiles as package data |
| `src/color_scheme_generator/cli/install_cmd.py` | CREATED — install command |
| `src/color_scheme_generator/cli/uninstall_cmd.py` | CREATED — uninstall command |
| `src/color_scheme_generator/adapters/docker/__init__.py` | CREATED — package marker |
| `src/color_scheme_generator/adapters/docker/Dockerfile.base` | CREATED — shared base image |
| `src/color_scheme_generator/adapters/docker/Dockerfile.custom` | CREATED — custom backend image |
| `src/color_scheme_generator/adapters/docker/Dockerfile.pywal` | CREATED — pywal backend image |
| `src/color_scheme_generator/adapters/docker/Dockerfile.wallust` | CREATED — wallust backend image |
| `tests/unit/cli/test_install_command.py` | CREATED — install CLI tests |
| `tests/unit/cli/test_uninstall_command.py` | CREATED — uninstall CLI tests |
| `tests/unit/adapters/test_image_lifecycle.py` | CREATED — adapter unit tests |
| `tests/unit/ports/test_interfaces.py` | MODIFIED — updated MockRuntime for protocol contract |
