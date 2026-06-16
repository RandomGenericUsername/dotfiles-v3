# OCI-Runtime Module Audit Report v2

**Date:** 2026-06-11
**Scope:** Full source, ports, adapters, domain, and factory layers

---

## Bugs

### 1. [CRITICAL] Missing import — `RuntimePreference` uses `RuntimeKind` without importing it

`ports/capabilities.py:11` — `kind: RuntimeKind` references `RuntimeKind` but never imports it. This will raise `NameError` at instantiation time.

**Fix plan:**

1. Add `from oci_runtime.domain.enums import RuntimeKind` to `ports/capabilities.py`.
2. Verify no other files in `ports/` reference domain types without imports — run `grep -r "RuntimeKind\|ContainerState\|RestartPolicy\|NetworkMode" src/oci_runtime/ports/` and audit results.
3. Add a test that instantiates `RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker")` to catch this class of error at import time.

---

### 2. [BUG] Exception hierarchy is semantically wrong

`domain/exceptions.py` — `ImageError`, `VolumeError`, and `NetworkError` all inherit from `ContainerError`. An image error is not a container error. They should be siblings under `OciError`.

**Fix plan:**

1. In `domain/exceptions.py`, re-parent `ImageError`, `VolumeError`, and `NetworkError` to inherit from `OciError` instead of `ContainerError`:

   ```python
   # Before
   class ImageError(ContainerError): ...
   class VolumeError(ContainerError): ...
   class NetworkError(ContainerError): ...

   # After
   class ImageError(OciError): ...
   class VolumeError(OciError): ...
   class NetworkError(OciError): ...
   ```

2. Update `domain/__init__.py` — no change needed since all names are already exported.
3. Audit all `except ContainerError` and `except ImageError` etc. catch blocks across the codebase to confirm they still behave correctly after the re-parenting.
4. In `adapters/managers/base.py:_check_result`, change the `not_found` parameter type from `Type[ContainerError]` to `Type[OciError]` so it can accept any domain error subclass.
5. Add a test that confirms `except OciError` catches all domain exceptions, and that `except ContainerError` no longer catches `ImageError`.
6. Run the full test suite and fix any tests that relied on the old hierarchy.

---

### 3. [BUG] `_default_parser_provider` creates throwaway provider instances

`factory.py:38-39` — Every call to `_default_parser_provider()` calls `_default_providers()[kind]`, constructing all providers fresh each time. The factory already stores providers in `self._providers`, so this should use those instead.

**Fix plan:**

1. Remove `_default_parser_provider` as a standalone function.
2. Change `RuntimeFactoryConfig.parser_provider` from `Callable[[RuntimeKind], Parsers]` to `Callable[[RuntimeKind, dict[RuntimeKind, RuntimeProvider]], Parsers]`, or better: make `RuntimeFactory` pass its own `self._providers` into the config resolution.
3. Simplest fix: in `_resolve_config`, when `parser_provider` is `None`, set it to a lambda that delegates to the factory's providers:

   ```python
   # In RuntimeFactory.__init__, after self._providers is set:
   if cfg is None or cfg.parser_provider is None:
       self._cfg = replace(self._cfg, parser_provider=self._create_parsers_from_providers)
   ```

4. Add a test that verifies `RuntimeFactory.create()` does not construct providers more than once.

---

### 4. [BUG] `CliTransport._read_stream` doesn't drain after process exit

`adapters/transport/cli.py:18-53` — When the process exits, data sitting in the pipe buffers can be lost.

**Fix plan:**

1. Add a drain loop after `process.poll() is not None` is detected in `_read_stream`, mirroring the `drain_after_exit` pattern in `pty.py`:

   ```python
   # After the main while loop in _read_stream:
   if drain_after_exit:
       while True:
           try:
               data = os.read(process.stdout.fileno(), 4096)
               if not data:
                   break
               stdout_acc.append(data)
               if on_output:
                   on_output(data, "stdout")
           except OSError:
               break
   ```

2. Actually, the cleaner approach: use `select`-based draining. After the main loop detects `process.poll() is not None`, keep selecting on stdout/stderr with short timeouts until both are closed (unregistered from selector).

3. Refactor `_read_stream` to set a `drain_after_exit` flag like pty, then do a final drain pass. Extract the drain pattern into a shared utility so `pty.py` and `cli.py` don't duplicate it.
4. Add a test that writes large output to a short-lived process and verifies all data is captured.

---

### 5. [BUG] `run_pty` always raises on non-zero exit code

`adapters/managers/pty.py:100-104` — Any non-zero exit raises `ContainerRuntimeError`, preventing callers from handling legitimate non-zero exit codes.

**Fix plan:**

1. Change `run_pty` to return `subprocess.CompletedProcess` on non-zero exit instead of raising. The caller should decide whether to treat non-zero as an error.
2. Remove lines 100-104 (`if proc.returncode != 0: raise ContainerRuntimeError(...)`).
3. Update the docstring on `Transport.execute_pty` (in `ports/transport.py`) to match: it currently says "Raises ContainerRuntimeError on non-zero exit" — change to "Returns a CompletedProcess with the returncode set."
4. Update `CliContainerManager.run()` (in `container.py:108-110`) which calls `self._transport.execute_pty(cmd)` — it currently relies on the exception. After the fix, check `result.returncode != 0` and handle accordingly, or let the caller decide.
5. Add tests for both zero and non-zero exit codes returning properly from `run_pty`.

---

### 6. [BUG] Podman `parse_list` silently drops port data

`adapters/parser/podman.py:80` — `ports=[]` is hardcoded while Docker's parser extracts ports from list output.

**Fix plan:**

1. Implement `_parse_ports_from_list` in `PodmanContainerParser`, mirroring `_parse_docker_ports_from_list` in docker.py. Podman's JSON list output has a similar `Ports` structure to Docker's.
2. Replace `ports=[]` in `parse_list` with `ports=self._parse_ports_from_list(item)`.
3. Examine real `podman ps --format json` output to confirm the exact JSON key names for ports in list format (likely `Ports` as a dict or list).
4. Add test vectors with Podman list JSON that includes port mappings.
5. Run integration tests against Podman to verify port data is captured.

---

### 7. [BUG] Docker `parse_list` name fallback produces empty string

`adapters/parser/docker.py:43` — When `Names` is `None`, `(item.get("Names") or ["/"])[0].lstrip("/")` produces `""`.

**Fix plan:**

1. Replace the fallback with a more defensive approach:

   ```python
   names = item.get("Names") or []
   name = names[0].lstrip("/") if names else item.get("Names", "") or "<unknown>"
   ```

2. Or raise `ParsingError` if the name field is truly missing/unparseable, since a container with no name is likely a malformed response.
3. Add test case with `Names=None` or `Names=[]` in the JSON and assert name is never empty string.
4. Apply the same fix pattern to `PodmanContainerParser.parse_list` line 75, which has the same `(item.get("Names") or ["/"])[0].lstrip("/")` pattern.

---

## Hexagonal Architecture Drifts

### 8. [DRIFT] `exec_pty` is a port method with adapter-only implementation

`ports/transport.py:33-38` — `execute_pty` on `Transport` ABC creates a downward import from transport to managers.

**Fix plan:**

1. **Option A (preferred): Move PTY entirely into transport.** Move `run_pty` from `adapters/managers/pty.py` into `adapters/transport/cli.py` as a private method on `CliTransport`. Remove the `adapters/managers/pty.py` file. The `execute_pty` method on `CliTransport` becomes self-contained.

2. **Option B: Extract to a separate port.** Create `ports/pty.py` with a `PtyTransport` ABC. Create `adapters/pty/cli.py` with `CliPtyTransport`. Have `ContainerManager` accept an optional `PtyTransport` instead of calling `self._transport.execute_pty()`.

3. Remove the `from oci_runtime.adapters.managers.pty import run_pty` import in `adapters/transport/cli.py:160`.
4. Update `ports/transport.py` — if Option A, keep `execute_pty` on `Transport`; if Option B, remove it from `Transport`.
5. Update `adapters/managers/container.py:108-110` to match the new API.
6. Add tests verifying no cross-adapter imports remain.

---

### 9. [DRIFT] `ExecResult` is defined in the ports layer

`ports/transport.py:7-11` — `ExecResult` is a domain value type that lives alongside the `Transport` ABC.

**Fix plan:**

1. Move `ExecResult` dataclass from `ports/transport.py` to `domain/types.py`.
2. Update `ports/transport.py` to import `from oci_runtime.domain.types import ExecResult`.
3. Update `domain/__init__.py` to export `ExecResult` (it's already there — verify).
4. Search for all imports of `ExecResult` from `oci_runtime.ports.transport` and change them to import from `oci_runtime.domain.types`.
5. Run the full test suite — this is a pure repositioning, no behavior change.

---

### 10. [DRIFT] `RuntimePreference` is in `ports/` but is a domain value object

`ports/capabilities.py:5-12` — `RuntimePreference` is a pure value object with no port behavior.

**Fix plan:**

1. Move `RuntimePreference` dataclass from `ports/capabilities.py` to `domain/types.py`.
2. Add `from oci_runtime.domain.enums import RuntimeKind` to `domain/types.py` (this also fixes bug #1 since `RuntimePreference` will now be where `RuntimeKind` is accessible).
3. Import `RuntimePreference` in `ports/capabilities.py` from its new location:

   ```python
   from oci_runtime.domain.types import RuntimePreference
   ```

4. Update `domain/__init__.py` to export `RuntimePreference`.
5. Update all import sites: `factory.py`, `adapters/discovery/cli.py`, and any tests.
6. Leave `RuntimeCapabilities` in `ports/capabilities.py` since it describes an adapter contract (but address its defaults per item #11).

---

### 11. [DRIFT] `RuntimeCapabilities` is in `ports/` with adapter-specific defaults

`ports/capabilities.py:16-22` — Docker-centric defaults like `tar_entry_name="Dockerfile"` and `supports_log_drivers=True` leak into the abstraction layer.

**Fix plan:**

1. Change `RuntimeCapabilities` defaults to be empty/minimal:

   ```python
   @dataclass(frozen=True)
   class RuntimeCapabilities:
       list_format_flags: list[str] = field(default_factory=list)
       needs_userns_keep_id: bool = False
       supports_log_drivers: bool = False          # was True
       tar_entry_name: str = ""                     # was "Dockerfile"
       default_run_flags: list[str] = field(default_factory=list)
       default_build_flags: list[str] = field_factory=list)
   ```

2. Update `DockerRuntimeProvider.capabilities()` and `PodmanRuntimeProvider.capabilities()` to explicitly pass all values, which they already do — so the change is purely to the defaults for safety.
3. Check that `image.py` build logic (which reads `self._caps.tar_entry_name`) handles the empty-string default gracefully when `tar_entry_name` is not explicitly set. It should — providers always set it.
4. Add a test that constructs `RuntimeCapabilities()` with no args and verifies it has no Docker-specific defaults.

---

### 12. [DRIFT] `Parsers` and `Managers` composition types in `ports/factory.py`

These frozen dataclasses are composition-root constructs, not port abstractions.

**Fix plan:**

1. Move `Parsers` and `Managers` dataclasses from `ports/factory.py` to `src/oci_runtime/factory.py` (the actual composition root).
2. Update `ports/factory.py` to only contain `RuntimeFactoryConfig`.
3. Update `ports/provider.py` — it currently imports `Parsers` and `Managers` from `ports.factory`. Change to import from `oci_runtime.factory`.
4. Update `adapters/provider/docker.py` and `adapters/provider/podman.py` — same import change.
5. Verify `ports/factory.py` still makes sense as a standalone port module. It should only contain config abstractions that define the contract for how the factory is configured.

---

### 13. [DRIFT] `RuntimeFactoryConfig` is DI configuration in the ports layer

`ports/factory.py:40-52` — Contains `Callable` factories for adapters. This is composition-root plumbing.

**Fix plan:**

1. Move `RuntimeFactoryConfig` from `ports/factory.py` to `src/oci_runtime/factory.py`.
2. After this and item #12, `ports/factory.py` should be empty or contain only port-level abstractions. If empty, leave it as a marker package or add a docstring explaining that the factory port is defined by the `RuntimeDiscovery` and `RuntimeProvider` interfaces.
3. Consolidate: `factory.py` (composition root) should contain `RuntimeFactory`, `RuntimeFactoryConfig`, `Parsers`, `Managers`, and the lazy-load functions. `ports/` should contain only the ABCs and domain-facing data contracts.
4. Update all imports from `oci_runtime.ports.factory` to `oci_runtime.factory` where appropriate.

---

### 14. [DRIFT] `ParsingError` in adapters but used across adapter boundaries

`adapters/parser/exceptions.py` — `ParsingError` is imported by `adapters/managers/*.py`. This creates a cross-adapter dependency.

**Fix plan:**

1. Move `ParsingError` from `adapters/parser/exceptions.py` to `domain/exceptions.py`.
2. Make `ParsingError` inherit from `OciError` (aligning with the domain exception hierarchy).
3. Update `domain/__init__.py` to export `ParsingError`.
4. Update all imports in `adapters/managers/container.py`, `adapters/managers/image.py`, `adapters/managers/network.py`, `adapters/managers/volume.py`, and `adapters/parser/base.py` to import from `oci_runtime.domain.exceptions`.
5. Delete `adapters/parser/exceptions.py`.
6. Update any test files that imported `ParsingError` from the old location.

---

### 15. [DRIFT] Empty `__init__.py` files suppress explicit API contracts

Both `ports/__init__.py` and `adapters/__init__.py` are empty.

**Fix plan:**

1. **`ports/__init__.py`** — Re-export the public port API:

   ```python
   from oci_runtime.ports.capabilities import RuntimeCapabilities, RuntimePreference
   from oci_runtime.ports.discovery import RuntimeDiscovery
   from oci_runtime.ports.engine import ContainerEngine
   from oci_runtime.ports.managers import ContainerManager, ImageManager, NetworkManager, VolumeManager
   from oci_runtime.ports.parsers import ContainerParser, ImageParser, NetworkParser, VolumeParser
   from oci_runtime.ports.provider import RuntimeProvider
   from oci_runtime.ports.transport import Transport
   ```

2. **`adapters/__init__.py`** — This should remain minimal. Adapters are implementation details; they shouldn't be re-exported from a package-level `__init__.py`. Add a docstring:

   ```python
   """Adapter implementations. Import concrete classes from their submodules."""
   ```

3. Verify no consumer code currently relies on `from oci_runtime.ports import ...` working without specific submodule paths (if they do, the re-exports make it work; if not, no breakage).

---

## Code Smells

### 16. [SMELL] `CliBaseManager._check_result` accepts overly broad type

`base.py:32` — `not_found: Type[ContainerError]` accepts any `ContainerError` subclass, but is called with `ImageNotFoundError`, `VolumeNotFoundError`, etc.

**Fix plan:**

1. After fixing bug #2 (exception hierarchy), change the type annotation:

   ```python
   from oci_runtime.domain.exceptions import OciError

   def _check_result(
       self,
       result: ExecResult,
       cmd: list[str],
       *,
       operation: str = "execute command",
       entity: str = "",
       not_found: Type[OciError],
   ) -> None:
   ```

2. This works because after the hierarchy fix, `ImageNotFoundError`, `ContainerNotFoundError`, etc., all inherit from `OciError`.
3. Optionally, create a `NotFoundError` mixin or protocol to narrow further to "not found" errors specifically, if desired.

---

### 17. [SMELL] `_create_tar` is a standalone function in the managers module

`adapters/managers/image.py:98-119` — Tar archive creation is a distinct I/O concern.

**Fix plan:**

1. Create `src/oci_runtime/adapters/build.py` (or `adapters/tar.py`) and move `_create_tar` there.
2. Rename from `_create_tar` to `create_build_tar` (drop leading underscore since it's now a module-level utility).
3. Update `adapters/managers/image.py` to import from the new location:

   ```python
   from oci_runtime.adapters.build import create_build_tar
   ```

4. Move any tar-related tests alongside the new module.
5. Consider making `create_build_tar` a method on `BuildContext` (in `domain/types.py`) that returns bytes — but only if domain types are allowed to have methods that do I/O (they currently don't, so the adapter module is the right home).

---

### 18. [SMELL] `parse_size_to_bytes` is a utility hiding in parser base

`adapters/parser/base.py:7-23` — Generic utility function not specific to parsing.

**Fix plan:**

1. Create `src/oci_runtime/domain/utils.py` (since it's a pure function with no I/O or adapter dependency).
2. Move `parse_size_to_bytes` there.
3. Update `adapters/parser/base.py` to import from the new location:

   ```python
   from oci_runtime.domain.utils import parse_size_to_bytes
   ```

4. Add unit tests for `parse_size_to_bytes` in `tests/unit/domain/`.
5. Update `adapters/parser/docker.py` which also imports it (via `from oci_runtime.adapters.parser.base import ...`).

---

### 19. [SMELL] `_parse_json_list` silently skips invalid lines

`adapters/parser/base.py:53-64` — NDJSON parsing silently drops lines that fail `json.loads()`.

**Fix plan:**

1. Add a `strict: bool = False` parameter to `_parse_json_list`. When `strict=True`, raise `ParsingError` on any line that fails to parse.
2. When `strict=False` (default, preserving current behavior), log a `warning`-level message using Python's `logging` module with the line content and index.
3. Add `import logging` and create `logger = logging.getLogger(__name__)` at module level.
4. Log format: `logger.warning("Skipping unparseable line %d in JSON list response: %s", idx, line[:100])`
5. Add tests for both strict and lenient modes.

---

### 20. [SMELL] `RuntimeFactory._providers` stored by reference

`factory.py:79` — Mutable dict can be mutated externally after construction.

**Fix plan:**

1. Change line 79 from:

   ```python
   self._providers = providers if providers is not None else _default_providers()
   ```

   to:

   ```python
   self._providers = dict(providers) if providers is not None else _default_providers()
   ```

2. This is a one-line change. `dict(providers)` creates a shallow copy, preventing external mutation.
3. Add a test that verifies mutating the original dict after construction doesn't affect the factory.

---

### 21. [SMELL] `ContainerManager.logs()` has no cancellation mechanism

`container.py:166-202` — The daemon thread continues running if the consumer stops iterating.

**Fix plan:**

1. Return a `Generator` that accepts a `StopIteration` or use `contextlib.contextmanager`-like pattern with cleanup:

   ```python
   def logs(self, container, follow=False, tail=None):
       ...
       stop_event = threading.Event()

       def _on_output(data, stream):
           if stop_event.is_set():
               raise StopIteration  # break out of execute
           queue.put(self._decode_stdout(data))

       # ... existing thread logic ...

       try:
           while True:
               chunk = queue.get(timeout=1.0)
               if chunk is None:
                   break
               yield chunk
       finally:
           stop_event.set()
           # Give the thread a moment to finish
           _thread.join(timeout=5)
   ```

2. Alternatively, add a `cancel()` method to the ABC and have `logs()` return an object that supports both iteration and `.cancel()`.
3. The simplest immediate fix: set `stop_event` in a `finally` block on the generator so the daemon thread sees it and can exit `execute()` early. This requires `Transport.execute()` to accept a `cancel_event` parameter.
4. Mark this as a follow-up — it requires interface changes to `Transport`.

---

### 22. [SMELL] Entrypoint handling is split and undocumented

`container.py:51,102-103` — `--entrypoint` gets only `config.entrypoint[0]`, while `entrypoint[1:]` is appended after the image name.

**Fix plan:**

1. Add a docstring on `RunConfig.entrypoint` explaining its semantics:

   ```python
   entrypoint: list[str] | None = None
   """Override the container entrypoint.
   
   If provided:
   - entrypoint[0] is passed to --entrypoint
   - entrypoint[1:] are appended after the image name (acts as CMD args)
   
   Matches Docker/Podman CLI behavior: `docker run --entrypoint /bin/sh myimage -c "ls"`
   results in entrypoint=["/bin/sh"] and command=["-c", "ls"].
   Actually passing entrypoint=["/bin/sh", "-c"] would make "-c" a CMD arg.
   """
   ```

2. Add an inline comment at the split point in `container.py`:

   ```python
   # Only the first element overrides --entrypoint; remaining elements
   # become CMD arguments appended after the image name (see RunConfig docs).
   if config.entrypoint and len(config.entrypoint) > 1:
       cmd.extend(config.entrypoint[1:])
   ```

3. Consider adding validation in `RunConfig.__post_init__` that `entrypoint` is non-empty if provided (since `entrypoint=[]` is meaningless).
4. Add a test case that verifies the exact CLI construction for `entrypoint=["/bin/sh", "-c"]`.

---

### 23. [SMELL] `_default_pty_output` writes directly to `sys.stdout`

`pty.py:12-14` — Default callback writes to stdout, making unit testing difficult.

**Fix plan:**

1. Remove `_default_pty_output` entirely.
2. Change `on_output` default to `None` in `run_pty` (it already is), and have the function handle `None` by buffering only — no stdout writing.
3. Move the "write to stdout" behavior to the caller. When `CliTransport.execute_pty` calls `run_pty`, it can pass a stdout-writing callback if desired.
4. Alternatively, accept an optional `output_stream: IO | None = None` parameter. If provided, write to it. This is more testable.

   ```python
   def run_pty(
       command: list[str],
       on_output: Callable[[bytes], None] | None = None,
   ) -> subprocess.CompletedProcess:
   ```

   The existing behavior already wraps `on_output` to buffer, so just remove `_default_pty_output` and the sys.stdout side effect.

5. Update tests that relied on the default stdout behavior.

---

### 24. [SMELL] `RuntimePreference` has a redundant `binary` field

`ports/capabilities.py:11-12` — `binary` almost always equals `kind.value`.

**Fix plan:**

1. Make `binary` optional with a default of `None`:

   ```python
   @dataclass(frozen=True)
   class RuntimePreference:
       kind: RuntimeKind
       binary: str | None = None

       @property
       def effective_binary(self) -> str:
           return self.binary if self.binary is not None else self.kind.value
   ```

2. Update all call sites that read `.binary` to use `.effective_binary`:
   - `factory.py:86` — `binary = preference.binary` → `binary = preference.effective_binary`
   - `adapters/discovery/cli.py:18` — same change
3. Update `CliTransport.__init__` and `CliRuntimeDiscovery` if they read `.binary`.
4. Update `RuntimeNotAvailableError` constructor in `discovery/cli.py` to use `.effective_binary`.
5. Add tests for both `binary=None` (defaults to kind) and `binary="/custom/path"` cases.

---

### 25. [SMELL] Duplicated provider logic between `DockerRuntimeProvider` and `PodmanRuntimeProvider`

`adapters/provider/docker.py` and `podman.py` are nearly identical — the only differences are `kind`, `capabilities()`, and parser class names.

**Fix plan:**

1. Create a base class `BaseCliRuntimeProvider` in `adapters/provider/base.py`:

   ```python
   class BaseCliRuntimeProvider(RuntimeProvider):
       _kind: RuntimeKind
       _container_parser_cls: type[ContainerParser]
       _image_parser_cls: type[ImageParser]
       _volume_parser_cls: type[VolumeParser]
       _network_parser_cls: type[NetworkParser]
       _container_manager_cls: type[CliContainerManager]
       _image_manager_cls: type[CliImageManager]
       _volume_manager_cls: type[CliVolumeManager]
       _network_manager_cls: type[CliNetworkManager]
       _capabilities: RuntimeCapabilities

       @property
       def kind(self) -> RuntimeKind:
           return self._kind

       def capabilities(self) -> RuntimeCapabilities:
           return self._capabilities

       def create_parsers(self) -> Parsers:
           return Parsers(
               container_parser=self._container_parser_cls(),
               image_parser=self._image_parser_cls(),
               volume_parser=self._volume_parser_cls(),
               network_parser=self._network_parser_cls(),
           )

       def create_managers(self, transport: Transport, caps: RuntimeCapabilities) -> Managers:
           parsers = self.create_parsers()
           return Managers(
               image_manager=self._image_manager_cls(transport, parsers.image_parser, caps),
               container_manager=self._container_manager_cls(transport, parsers.container_parser, caps),
               volume_manager=self._volume_manager_cls(transport, parsers.volume_parser, caps),
               network_manager=self._network_manager_cls(transport, parsers.network_parser, caps),
           )
   ```

2. Simplify `DockerRuntimeProvider` and `PodmanRuntimeProvider` to just declare their class attributes:

   ```python
   class DockerRuntimeProvider(BaseCliRuntimeProvider):
       _kind = RuntimeKind.DOCKER
       _container_parser_cls = DockerContainerParser
       # ... etc
       _capabilities = RuntimeCapabilities(...)
   ```

3. This reduces each provider from ~45 lines to ~10 lines.
4. Add tests that verify both providers still produce the correct `Parsers` and `Managers`.

---

### 26. [SMELL] `domain/types.py` imports `sys` for `RunConfig.effective_tty`

`domain/types.py:1,86` — `sys.stdout.isatty()` is a side-effectful I/O check in a domain dataclass.

**Fix plan:**

1. Remove `import sys` from `domain/types.py`.
2. Remove the `effective_tty` property from `RunConfig`:

   ```python
   # Remove:
   @property
   def effective_tty(self) -> bool:
       return self.tty or (self.auto_tty and sys.stdout.isatty())
   ```

3. Change `auto_tty` semantics. Instead of "automatically detect TTY", make it a flag that the **adapter layer** evaluates:

   ```python
   # In RunConfig:
   auto_tty: bool = False  # Set by caller; adapter resolves it
   ```

4. Add a method on `ContainerManager` or `Transport` that resolves the effective TTY:

   ```python
   # In CliContainerManager:
   def _resolve_tty(self, config: RunConfig) -> bool:
       return config.tty or (config.auto_tty and sys.stdout.isatty())
   ```

5. Update `CliContainerManager.run()` to call `self._resolve_tty(config)` instead of `config.effective_tty`.
6. Update the `run()` method's detach/tty check to use the resolved value.
7. Add tests that verify TTY resolution with mocked `sys.stdout.isatty`.

---

## Summary

| Category       | Count | Severity               |
|----------------|-------|------------------------|
| Bugs           | 7     | 1 critical, 3 high, 3 medium |
| Architecture drifts | 8 | 4 high, 4 medium       |
| Code smells    | 11    | 6 medium, 5 low       |

## Top 3 Priorities

1. **Fix the missing `RuntimeKind` import in `capabilities.py`** (runtime crash)
2. **Fix the exception hierarchy** (`ImageError`/`VolumeError`/`NetworkError` should not extend `ContainerError`)
3. **Move `ExecResult`, `RuntimePreference`, `ParsingError` to `domain/`** and move `Parsers`/`Managers`/`RuntimeFactoryConfig` out of `ports/`