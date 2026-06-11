# OCI-Runtime Phase 3 — Implementation Plan

**Prerequisite:** Phases 1 & 2 complete. 645 tests passing.
**Goal:** Apply all Phase 3 architectural changes. No backwards compatibility required.

---

## A1 — Refactor `run_pty()` with callback pattern

### What
`run_pty()` currently writes directly to `sys.stdout.buffer`, making it untestable. Add an `on_output` callback parameter with a default that writes to stdout.

### Files to change
1. **`src/oci_runtime/adapters/managers/pty.py`**
   - Change signature:
     ```python
     def run_pty(
         command: list[str],
         on_output: Callable[[bytes], None] | None = None,
     ) -> subprocess.CompletedProcess:
     ```
   - Replace every `sys.stdout.buffer.write(chunk)` / `sys.stdout.buffer.flush()` with:
     ```python
     if on_output is None:
         on_output = _default_pty_output
     
     # ... inside the read loops:
     on_output(chunk)
     ```
   - Add module-level default:
     ```python
     def _default_pty_output(data: bytes) -> None:
         sys.stdout.buffer.write(data)
         sys.stdout.buffer.flush()
     ```

2. **`src/oci_runtime/adapters/managers/container.py:103-104`**
   - The `run()` method calls `run_pty(cmd)`. No change needed — default callback writes to stdout, preserving current behavior.

3. **`tests/unit/adapters/test_cli_pty.py`**
   - Update existing tests that assert on stdout capture to use an `on_output` callback that collects into a list.
   - Add new test: `test_run_pty_calls_on_output_callback`.
   - Add new test: `test_run_pty_default_writes_to_stdout` (uses monkeypatch on `sys.stdout.buffer`).

### Validation
- `uv run pytest tests/unit/adapters/test_cli_pty.py -v`
- Full suite: `uv run pytest tests/ -v`

---

## A2 — Distinguish stdout vs stderr in streaming `on_output`

### What
Change `on_output` signature from `Callable[[bytes], None]` to `Callable[[bytes, str], None]` where the second arg is `"stdout"` or `"stderr"`.

### Files to change
1. **`src/oci_runtime/ports/transport.py`**
   - Change `ExecResult` signature line and `Transport.execute`:
     ```python
     on_output: Callable[[bytes, str], None] | None = None,
     ```
   - The second parameter is `stream: Literal["stdout", "stderr"]`.

2. **`src/oci_runtime/adapters/transport/cli.py`**
   - In `_read_stream`, change signature:
     ```python
     on_output: Callable[[bytes, str], None] | None = None,
     ```
   - Change the callback invocations:
     ```python
     if on_output:
         on_output(data, "stdout")   # was: on_output(data)
     # ...
     if on_output:
         on_output(data, "stderr")   # was: on_output(data)
     ```
   - In `execute()`, update the `_read_stream` call — no change needed since it passes `on_output` through.

3. **`src/oci_runtime/adapters/managers/container.py`** — `logs()` method
   - The `_on_output` closure at line ~179:
     ```python
     # BEFORE:
     def _on_output(data: bytes) -> None:
         queue.put(self._decode_stdout(data))
     # AFTER:
     def _on_output(data: bytes, stream: str) -> None:
         queue.put(self._decode_stdout(data))
     ```
   - The stream info is available but `logs()` doesn't use it to separate stdout/stderr. If desired later, it can now.

4. **`tests/helpers/mock_transport.py`** — `RecordingTransport.execute()`
   - Update type annotation:
     ```python
     def execute(self, command, *, timeout=None, input_data=None, stream=False, on_output=None):
     ```
   - When calling `on_output` in stream mode, pass stream identifier:
     ```python
     for chunk in self._stream_responses[key]:
         on_output(chunk, "stdout")
     ```

5. **`tests/unit/adapters/test_cli_transport.py`** — `TestExecuteStreaming` and `TestReadStream`
   - Update any `on_output` callbacks to accept 2 args.
   - Search for all `on_output` usages in test files and update signatures.

6. **`tests/unit/ports/test_transport.py`** — update the abstract method test if it checks `on_output` signature.

### Validation
- `uv run pytest tests/ -v` — all tests must pass
- Grep for `on_output` across entire codebase to find any missed call sites.

---

## A3 — Export domain types from `domain/__init__.py`

### What
Populate the empty `domain/__init__.py` so `from oci_runtime.domain import X` works.

### Files to change
1. **`src/oci_runtime/domain/__init__.py`**
   ```python
   from oci_runtime.domain.enums import ContainerState, NetworkMode, RestartPolicy, RuntimeKind
   from oci_runtime.domain.exceptions import (
       ContainerError,
       ContainerNotFoundError,
       ContainerRuntimeError,
       ImageError,
       ImageNotFoundError,
       NetworkError,
       NetworkNotFoundError,
       OciError,
       ParsingError,
       RuntimeNotAvailableError,
       VolumeError,
       VolumeNotFoundError,
   )
   from oci_runtime.domain.types import (
       BuildContext,
       ContainerInfo,
       ExecOutput,
       ImageInfo,
       NetworkInfo,
       PortMapping,
       RunConfig,
       VolumeInfo,
       VolumeMount,
   )

   __all__ = [
       "BuildContext",
       "ContainerError",
       "ContainerInfo",
       "ContainerRuntimeError",
       "ContainerState",
       "ExecOutput",
       "ImageError",
       "ImageInfo",
       "ImageNotFoundError",
       "NetworkError",
       "NetworkInfo",
       "NetworkMode",
       "NetworkNotFoundError",
       "OciError",
       "ParsingError",
       "PortMapping",
       "RestartPolicy",
       "RunConfig",
       "RuntimeKind",
       "RuntimeNotAvailableError",
       "VolumeError",
       "VolumeInfo",
       "VolumeMount",
       "VolumeNotFoundError",
   ]
   ```

2. **Tests** — Add a new test file:
   **`tests/unit/domain/test_domain_init.py`**
   ```python
   def test_domain_exports_enums():
       from oci_runtime.domain import ContainerState, RuntimeKind, RestartPolicy, NetworkMode

   def test_domain_exports_exceptions():
       from oci_runtime.domain import OciError, ContainerError, ParsingError

   def test_domain_exports_types():
       from oci_runtime.domain import ContainerInfo, RunConfig, ExecOutput

   def test_domain_star_import():
       from oci_runtime.domain import *
       assert "ContainerState" in dir()
   ```

### Validation
- Run new domain init tests
- `uv run pytest tests/ -v`

---

## A4 — Rename `ContainerManager.exec()` → `exec_container()`

### What
Rename the `exec` method to `exec_container` to avoid shadowing Python's builtin `exec()`.

### Files to change (in order)
1. **`src/oci_runtime/ports/managers.py`** line 72
   - `def exec(self, ...)` → `def exec_container(self, ...)`

2. **`src/oci_runtime/adapters/managers/container.py`** line 201
   - `def exec(self, ...)` → `def exec_container(self, ...)`

3. **All test files that call `.exec(`** — search results show 5 call sites:
   - `tests/integration/boundary/test_empty_outputs.py:92` — change `mgr.exec(` → `mgr.exec_container(`
   - `tests/unit/ports/test_container_manager_contract.py:95` — change `mgr.exec(` → `mgr.exec_container(`
   - `tests/integration/functional/test_workflows.py:121,165` — change `.exec(` → `.exec_container(`
   - `tests/integration/integration/test_manager_commands.py:274,282` — change `.exec(` → `.exec_container(`

4. **Any contract/compliance tests** that assert on abstract method names — check `test_container_manager_contract.py` for `has_abstract_exec` or similar.

### Validation
- Grep for `\bexec\b` in all `.py` files to find any remaining call sites
- `uv run pytest tests/ -v`

---

## A5 — Rename `all` parameter → `show_all` in list/prune methods

### What
Rename the `all` parameter (shadows builtin `all()`) to `show_all` in:
- `ContainerManager.list(all=...)` 
- `ImageManager.prune(all=...)`

### Files to change (in order)
1. **`src/oci_runtime/ports/managers.py`** line 66
   - `def list(self, all: bool = False, ...)` → `def list(self, show_all: bool = False, ...)`

2. **`src/oci_runtime/ports/managers.py`** line 40
   - `def prune(self, all: bool = False) -> dict[str, int]:` → `def prune(self, show_all: bool = False) -> dict[str, int]:`

3. **`src/oci_runtime/adapters/managers/container.py`** line 153
   - `def list(self, all: bool = False, ...)` → `def list(self, show_all: bool = False, ...)`
   - `if all:` → `if show_all:`

4. **`src/oci_runtime/adapters/managers/image.py`** line 91
   - `def prune(self, all: bool = False) -> dict[str, int]:` → `def prune(self, show_all: bool = False) -> dict[str, int]:`
   - `if all:` → `if show_all:`

5. **All test call sites** — search for `(all=True)` and `(all=False)`:
   - `tests/integration/integration/test_manager_commands.py:112` — `mgr.prune(all=True)` → `mgr.prune(show_all=True)`
   - `tests/integration/integration/test_manager_commands.py:243` — `mgr.list(all=True)` → `mgr.list(show_all=True)`
   - Any other test files with `.list(all=` or `.prune(all=`

6. **Contract tests** — `test_container_manager_contract.py`, `test_image_manager_contract.py` — update param names.

### Validation
- Grep for `\ball\b` in method signatures to catch any remaining
- `uv run pytest tests/ -v`

---

## A6 — Make `_create_tar` reproducible

### What
Set explicit `uid=0`, `gid=0`, `mtime=0` on `TarInfo` objects for deterministic builds.

### Files to change
1. **`src/oci_runtime/adapters/managers/image.py`** — `_create_tar` function, lines 106-113:
   ```python
   # BEFORE:
   info = tarfile.TarInfo(name=tar_entry_name)
   content = build_file_content.encode("utf-8")
   info.size = len(content)
   tar.addfile(info, io.BytesIO(content))
   for path, data in files.items():
       info = tarfile.TarInfo(name=path)
       info.size = len(data)
       tar.addfile(info, io.BytesIO(data))

   # AFTER:
   info = tarfile.TarInfo(name=tar_entry_name)
   content = build_file_content.encode("utf-8")
   info.size = len(content)
   info.uid = 0
   info.gid = 0
   info.mtime = 0
   tar.addfile(info, io.BytesIO(content))
   for path, data in files.items():
       info = tarfile.TarInfo(name=path)
       info.size = len(data)
       info.uid = 0
       info.gid = 0
       info.mtime = 0
       tar.addfile(info, io.BytesIO(data))
   ```

2. **Tests** — add a test in `test_cli_image_manager.py`:
   ```python
   def test_create_tar_is_deterministic(self):
       from oci_runtime.adapters.managers.image import _create_tar
       tar1 = _create_tar("FROM alpine", {"app.py": b"print('hi')"})
       tar2 = _create_tar("FROM alpine", {"app.py": b"print('hi')"})
       assert tar1 == tar2
   ```

### Validation
- `uv run pytest tests/ -v`

---

## A7 — Separate `_resolve_config` provider registration from config defaults

### What
Move auto-registration of default providers out of `_resolve_config()` into a separate function, called explicitly from `RuntimeFactory.__init__`.

### Files to change
1. **`src/oci_runtime/factory.py`**
   - Extract the provider auto-registration block from `_resolve_config()` into a standalone function:
     ```python
     def _ensure_default_providers() -> None:
         if not _PROVIDER_REGISTRY:
             from oci_runtime.adapters.provider.docker import DockerRuntimeProvider
             from oci_runtime.adapters.provider.podman import PodmanRuntimeProvider
             register_provider(DockerRuntimeProvider())
             register_provider(PodmanRuntimeProvider())
     ```
   - Remove the provider registration block from `_resolve_config()`.
   - In `RuntimeFactory.__init__`, call `_ensure_default_providers()`:
     ```python
     def __init__(
         self,
         config: RuntimeFactoryConfig | None = None,
         providers: dict[RuntimeKind, RuntimeProvider] | None = None,
     ):
         _ensure_default_providers()
         self._cfg = _resolve_config(config)
         self._providers = providers if providers is not None else _PROVIDER_REGISTRY
     ```
   - `_resolve_config()` now only handles config defaults (transport_factory, runtime_cls, etc.), not provider registration.

2. **Tests** — tests that `RuntimeFactory()` auto-registers providers should still pass. Tests that manually clear `_PROVIDER_REGISTRY` may need to call `_ensure_default_providers()` or create a factory (which calls it).

### Validation
- `uv run pytest tests/ -v`

---

## Implementation Order

Execute in this order (each item is independently testable):

1. **A3** — Domain exports (simplest, zero risk, no API changes to existing code)
2. **A6** — `_create_tar` reproducibility (isolated, zero risk)
3. **A1** — `run_pty()` callback (isolated to pty module + its tests)
4. **A4** — Rename `exec` → `exec_container` (grep-friendly, mechanical)
5. **A5** — Rename `all` → `show_all` (grep-friendly, mechanical)
6. **A2** — `on_output` stream distinction (touches Transport ABC, widest impact)
7. **A7** — Separate provider registration (factory internals, low risk)

After each item:
1. `uv run pytest tests/ -v`
2. Grep for old names/patterns to confirm full replacement
3. Move to next item only after all tests pass

---

## Change Log

| Phase | Item | Status | Tests | Notes |
|-------|------|--------|-------|-------|
| 1 | F1 | [x] DONE | 645 pass | Replaced raw .decode() with _decode_stdout() |
| 1 | F2 | [x] DONE | 645 pass | Moved import re to module top |
| 1 | F3 | [x] DONE | 645 pass | Changed default from 1 to 0 |
| 1 | F4 | [x] DONE | 645 pass | All Docker is_not_found_error now use .lower() |
| 1 | F5 | [x] DONE | 645 pass | Added operation param to volume/network _check_result |
| 1 | F6 | [x] DONE | 645 pass | Cleaned up version() variable |
| 1 | F7 | [x] DONE | 645 pass | Fixed ExecResult to use bytes |
| 2 | S1 | [x] DONE | 645 pass | RuntimeKind now StrEnum |
| 2 | S2 | [x] DONE | 646 pass | OciError base added, ParsingError is sibling |
| 2 | S3 | [x] DONE | 645 pass | dataclasses.replace() instead of object.__setattr__ |
| 2 | S4 | [x] DONE | 645 pass | Parsers fields renamed to full names |
| 2 | S5 | [x] DONE | 645 pass | Provider registry injectable into RuntimeFactory |
| 2 | S6 | [x] DONE | 645 pass | detach+tty validation moved before cmd build |
| 2 | S7 | [x] DONE | N/A | Handled by F1+F6 |
| 2 | S8 | [x] DONE | 645 pass | is_available() now uses transport.probe() |
| 3 | A1 | [ ] | | run_pty callback pattern |
| 3 | A2 | [ ] | | on_output stream distinction |
| 3 | A3 | [ ] | | Domain __init__.py exports |
| 3 | A4 | [ ] | | exec → exec_container |
| 3 | A5 | [ ] | | all → show_all |
| 3 | A6 | [ ] | | _create_tar reproducible |
| 3 | A7 | [ ] | | Separate provider registration |