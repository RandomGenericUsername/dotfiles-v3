## Context

`oci-runtime` is a runtime-agnostic OCI container-management module living at `src/shared/oci-runtime/`. It wraps the `docker` and `podman` CLIs behind ports so application code depends on abstractions (`domain ← ports ← adapters`, with the factory as the composition root). The v2 audit remediation fixed 43 issues and added an architecture linter. The v3 audit surfaced **8 critical bugs that the test suite actively masks**, plus drift in layering enforcement and docs.

Six decisions were taken by the user in the decision round (carried over from v3 proposal):
1. `host_ip="0.0.0.0"` is treated as a **real bind** — never coalesced.
2. `ProcessPipeReader` becomes **strict** (raise `TypeError` if `fileno()` unavailable).
3. **Delete** the `Managers` aggregate and fix the doc drift — do not revive `create_managers`.
4. `version()` raises **`OciError`** with `command`/`exit_code`/`stderr` attached.
5. **Zero** adapter→adapter imports — full strict hexagonal.
6. Transports require injected collaborators — **no internal fallbacks**.

Two new decisions driven by the pure-hexagonal analysis:
7. **No shared adapter bases in ports** — `ports/parser_base`, `manager_base`, `provider_base` are not created. Instead, adapters implement port ABCs directly and receive helpers via DI or domain functions.
8. **New helper ports `ResultChecker` + `ListExecutor`** — shared CLI patterns extracted to proper ports with pure ABCs, implemented by dedicated adapters injected by the factory.

Constraints the design honors:
- Public `__all__` lives in `src/oci_runtime/__init__.py` — kept stable.
- Domain layer stays stdlib-only — verified by `tests/architecture/test_layering.py`.
- `make check` (lint + format-check + test) stays the default CI gate.
- 840 existing tests must remain green end-to-end at every phase boundary.

## Goals / Non-Goals

**Goals:**
- Eliminate every critical bug surfaced in the v3 audit (A1–A8).
- Achieve **zero adapter→adapter structural imports**; enforce via architecture linter.
- Ports contain **only pure ABCs** (abstract methods, zero implementation) and pure-stdlib value types (dataclasses, enums).
- All pure-stdlib shared logic moves to `domain/` — adapters call domain functions directly.
- Shared CLI orchestration patterns (result checking, list command execution) extracted to helper ports (`ResultChecker`, `ListExecutor`) with dedicated adapters injected by the factory.
- Make every test assertion match correct behavior — no test forwards a bug.
- Remove all audit-flagged dead code.
- Align `ARCHITECTURE.md` and in-code docstrings to source-of-truth behavior.
- Preserve the public API (`__all__`); only internal constructor signatures change.

**Non-Goals:**
- No new container-runtime support (nerdctl / containerd).
- No Python-version bump (still `>=3.12`).
- No new third-party dependencies — stdlib only.
- No CI workflow changes; `Makefile` untouched.
- No public-API breaking change to domain types or ports.

## Framework: Where Code Belongs

Every piece of code in this change is placed according to a strict classification:

| Layer | Contents | Dependency rule | Examples |
|-------|----------|-----------------|----------|
| `domain/` | Pure functions. Stdlib only. No I/O. No port/adapter imports. | stdlib only | `parse_json_item()`, `build_list_command()`, `check_cli_result()` |
| `ports/` | Pure ABCs with abstract methods only. Pure-stdlib value types (dataclasses, enums). Pure-stdlib coordination classes with no side effects. Pure-stdlib functions. | `domain` + stdlib only | `ContainerParser`, `ContainerManager`, `ResultChecker`, `ListExecutor[T]`, `CancellationToken`, `compose_tokens()`, `CompositeCancellationToken` |
| `adapters/` | Concrete implementations. I/O, subprocess, file access. | `domain` + `ports` (never sibling adapters) | `DockerContainerParser`, `CliContainerManager`, `ProcessPipeReader` |
| `factory.py` | Composition root. Wires adapters to ports. | anything (single exception point) | `RuntimeFactory.create()` |

## Decisions

### D1. Pure-stdlib helpers move to `domain/`

Every pure-stdlib function currently in `adapters/` moves to a dedicated `domain/` module:

| Current location | New location | Functions |
|---|---|---|
| `adapters/_tar.py` | `domain/build_tar.py` | `create_build_tar`, `_validate_tar_path` |
| `adapters/_utils.py` | `domain/size_parsing.py` | `parse_size_to_bytes`, `coerce_size`, `safe_int` |
| `adapters/parser/base.py:_parse_json_item,_parse_json_list` | `domain/json_parsing.py` | `parse_json_item`, `parse_json_list` |
| `adapters/parser/base.py:is_not_found_error,is_auth_error` (matching logic) | `domain/error_matching.py` | `matches_any_pattern(text, patterns) → bool` |
| `adapters/parser/base.py:parse_prune` (parsing logic) | `domain/prune_parsing.py` | `parse_prune_result(raw) → PruneResult` |
| (new, extracted from `_check_result`) | `domain/result_checking.py` | `check_cli_result(result, cmd, *, operation, entity, not_found_error, generic_error, auth_error, is_auth, is_not_found) → None` |
| (new, extracted from `_execute_list`) | `domain/list_command.py` | `build_list_command(binary, subcommand, format_flags, show_all, filters) → list[str]` |
| (new, extracted from `_decode_bytes`) | `domain/encoding.py` | `safe_decode(data: bytes) → str` |

Domain modules are addressable from any adapter (`from oci_runtime.domain.json_parsing import parse_json_item`). Zero I/O, zero port imports, zero adapter imports.

After the move, the linter enforces `adapters → {domain, ports}` with no exceptions.

### D2. Ports contain only pure ABCs (zero shared adapter bases)

The v3 plan proposed moving `BaseCliParser`, `CliBaseManager`, and `BaseCliRuntimeProvider` to `ports/` with their implementation intact. **This design rejects that approach.** Instead:

- **No `ports/parser_base.py`** — `BaseCliParser` is deleted. Each concrete parser (`DockerContainerParser`, etc.) implements the existing port ABCs (`ContainerParser`, `ImageParser`, `VolumeParser`, `NetworkParser`) directly, calling domain helpers for shared logic.
- **No `ports/manager_base.py`** — `CliBaseManager` is deleted. Each concrete manager (`CliContainerManager`, etc.) implements the existing port ABCs (`ContainerManager`, `ImageManager`, `VolumeManager`, `NetworkManager`) directly, receiving `ResultChecker` and `ListExecutor` helpers via constructor injection.
- **No `ports/provider_base.py`** — `BaseCliRuntimeProvider` is deleted. Each provider (`DockerRuntimeProvider`, `PodmanRuntimeProvider`) implements the existing `RuntimeProvider` port directly, receiving parser classes from the factory via constructor injection.

This ensures ports remain pure — every file under `ports/` contains only ABCs with abstract methods, frozen dataclasses, and pure-stdlib utility functions. No concrete methods, no adapter logic.

The cost of this decision is quantified below in D6/D7/D8.

### D3. `ResultChecker` port — shared CLI result checking as a pure ABC

The pattern "execute command, check return code, decode stderr, raise appropriate exception" repeats in every manager method (~30 call sites across 4 managers). It becomes a proper port:

```python
# ports/result_checker.py
from abc import ABC, abstractmethod
from oci_runtime.domain.types import RawExecResult
from oci_runtime.domain.exceptions import OciError


class ResultChecker(ABC):
    @abstractmethod
    def check(
        self,
        result: RawExecResult,
        cmd: list[str],
        *,
        operation: str = "execute",
        entity: str = "",
        not_found_error: type[OciError] | None = None,
    ) -> None:
        """Check a CLI result and raise the appropriate OciError subclass.

        Raises:
            AuthError: if self._auth_error is set and stderr matches auth pattern
            NotFoundError: if stderr matches the not-found pattern
            GenericError: for any non-zero exit without specific match
        """
```

The port is pure — three parameters, one abstract method, depends only on domain types. No adapter logic leaks into the port.

**Adapter implementation:**

```python
# adapters/helpers/result_checker.py
from collections.abc import Callable
from oci_runtime.domain.encoding import safe_decode
from oci_runtime.domain.exceptions import OciError
from oci_runtime.ports.result_checker import ResultChecker


class CliResultChecker(ResultChecker):
    def __init__(
        self,
        generic_error: type[OciError],
        not_found_error: type[OciError],
        is_not_found: Callable[[str], bool],
        *,
        auth_error: type[OciError] | None = None,
        is_auth: Callable[[str], bool] | None = None,
    ):
        self._generic_error = generic_error
        self._not_found_error = not_found_error
        self._is_not_found = is_not_found
        self._auth_error = auth_error
        self._is_auth = is_auth

    def check(
        self,
        result: RawExecResult,
        cmd: list[str],
        *,
        operation: str = "execute",
        entity: str = "",
        not_found_error: type[OciError] | None = None,
    ) -> None:
        if result.returncode == 0:
            return
        not_found_error = not_found_error or self._not_found_error
        stderr_str = safe_decode(result.stderr)

        if self._auth_error and self._is_auth and self._is_auth(stderr_str):
            raise self._auth_error(entity)

        if self._is_not_found(stderr_str):
            raise not_found_error(entity)

        raise self._generic_error(
            message=f"Failed to {operation} | {stderr_str}",
            command=cmd,
            exit_code=result.returncode,
            stderr=stderr_str,
        )
```

**Key design properties:**
- The `not_found_error` method parameter allows `run()` to override with `ImageNotFoundError` (a container method that checks for an image).
- The `is_not_found` and `is_auth` callables are sourced from the parser at wiring time. The `ResultChecker` never imports a parser type — it depends on `Callable[[str], bool]`.
- The adapter only depends on domain + ports. No adapter imports. ✅
- Each manager gets its own `ResultChecker` instance wired by the factory with its specific error types and parser callables.

### D4. `ListExecutor[T]` port — shared list orchestration as a pure ABC

The "build list command, execute, check, parse" pattern repeats identically in all 4 managers' `list()` methods. It becomes a generic port:

```python
# ports/list_executor.py
from typing import Generic, TypeVar
from abc import ABC, abstractmethod

T = TypeVar("T")


class ListExecutor(ABC, Generic[T]):
    @abstractmethod
    def execute_list(
        self,
        subcommand: list[str],
        entity_type: str,
        *,
        show_all: bool = False,
        filters: dict[str, str] | None = None,
    ) -> list[T]:
        """Build, execute, check, and parse a list command.

        Returns parsed domain objects of type T.
        """
```

**Adapter implementation:**

```python
# adapters/helpers/list_executor.py
from collections.abc import Callable
from typing import Generic, TypeVar

from oci_runtime.domain.list_command import build_list_command
from oci_runtime.domain.encoding import safe_decode
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.list_executor import ListExecutor
from oci_runtime.ports.result_checker import ResultChecker
from oci_runtime.ports.transport import Transport

T = TypeVar("T")


class CliListExecutor(ListExecutor[T]):
    def __init__(
        self,
        transport: Transport,
        caps: RuntimeCapabilities,
        result_checker: ResultChecker,
        parse_list: Callable[[str], list[T]],
    ):
        self._transport = transport
        self._caps = caps
        self._result_checker = result_checker
        self._parse_list = parse_list

    def execute_list(
        self,
        subcommand: list[str],
        entity_type: str,
        *,
        show_all: bool = False,
        filters: dict[str, str] | None = None,
    ) -> list[T]:
        cmd = build_list_command(
            self._transport.get_runtime_binary(),
            subcommand,
            self._caps.list_format_flags,
            show_all,
            filters,
        )
        result = self._transport.execute(cmd)
        self._result_checker.check(
            result, cmd, operation=f"list {entity_type}",
        )
        return self._parse_list(safe_decode(result.stdout))
```

**Key design properties:**
- `T` binds at wiring time: `CliListExecutor[ContainerInfo]` for containers, `CliListExecutor[ImageInfo]` for images, etc.
- Receives `ResultChecker` from the factory — shares the same instance used by the manager for non-list operations, ensuring consistent error types.
- The adapter depends only on ports + domain. No adapter imports. ✅
- Each manager's `list()` becomes a 1-line delegation.

**Composition hierarchy:**
```
Factory
  └─→ CliResultChecker(generic_error=ContainerRuntimeError, ...)   ← 1 per manager
  │     ├─→ CliContainerManager(result_checker=...)                 ← used by run(), pull(), etc.
  │     └─→ CliListExecutor[ContainerInfo](result_checker=...)      ← shared instance for list()
  │
  ListExecutor uses ResultChecker internally for the check step,
  then parses the output via parse_list callback.
```

**Validated by prototype:** A `CliListExecutor` was traced through the full `list()` flow:
1. `build_list_command("docker", ["container", "list"], ("--format", "{{json .}}"), False, {"name": "web"})` → `["docker", "container", "list", "--format", "{{json .}}", "--filter", "name=web"]`
2. `transport.execute(cmd)` returns `RawExecResult(0, b'[...]', b'')`
3. `result_checker.check(...)` returns (exit 0, no error)
4. `parse_list(safe_decode(result.stdout))` returns `list[ContainerInfo]`

The prototype validated that all 4 manager types work with the same `CliListExecutor` adapter, differing only in the `parse_list` callable.

### D5. `PipeReader` port — pure ABC (from v3 plan, kept unchanged)

`ports/pipe_reader.py` defines a pure ABC with three abstract methods. `ProcessPipeReader` in `adapters/_process_reader.py` implements it. No concrete logic in ports. Identical to v3 plan.

```python
class PipeReader(ABC):
    @abstractmethod
    @classmethod
    def from_process(cls, process) -> "PipeReader": ...
    @abstractmethod
    @classmethod
    def from_fds(cls, primary_fd, secondary_fd) -> "PipeReader": ...
    @abstractmethod
    def read(self, on_primary=None, on_secondary=None, cancel_token=None) -> tuple[list[bytes], list[bytes]]: ...
```

### D6. Cancellation — `CompositeCancellationToken` + `compose_tokens` move to `ports/cancellation.py`

`CompositeCancellationToken` is pure logic (delegates to children, no I/O, no threads). `compose_tokens` is a pure function. Both move to `ports/cancellation.py`:

```python
# ports/cancellation.py
class CancellationToken(ABC):
    @abstractmethod
    def cancel(self) -> None: ...
    @property
    @abstractmethod
    def is_cancelled(self) -> bool: ...


class CompositeCancellationToken(CancellationToken):
    """Cancelled when ANY child token is cancelled. Pure logic, no I/O."""
    def __init__(self, *children: CancellationToken) -> None:
        self._children = children
    def cancel(self) -> None:
        for c in self._children:
            c.cancel()
    @property
    def is_cancelled(self) -> bool:
        return any(c.is_cancelled for c in self._children)


def compose_tokens(*tokens: CancellationToken | None) -> CancellationToken | None:
    """Combine optional tokens into a single CompositeCancellationToken.
    Returns None if all tokens are None. Filters out None values."""
    active = [t for t in tokens if t is not None]
    if not active:
        return None
    if len(active) == 1:
        return active[0]
    return CompositeCancellationToken(*active)
```

`ThreadCancellationToken` and `DeadlineCancellationToken` remain in `adapters/_cancellation.py` (they manage threading state). Transports import `compose_tokens` from `ports.cancellation` (allowed) and receive `deadline_factory` via constructor injection:

```python
# factory.py wires:
deadline_factory=lambda t: DeadlineCancellationToken(t),  # injected into transports
```

### D7. Parser decomposition — self-contained implementations

Each concrete parser becomes self-contained, directly implementing the port ABCs and calling domain helpers.

**Before (current):**
```python
class DockerContainerParser(BaseCliParser, ContainerParser):
    _not_found_patterns = ("no such container",)
    def parse_inspect(self, raw):
        item = self._parse_json_item(raw)      # inherited from BaseCliParser
        ...
    def is_not_found_error(self, stderr):
        return super().is_not_found_error(stderr)  # inherited
```

**After:**
```python
class DockerContainerParser(ContainerParser):
    _not_found_patterns = ("no such container",)

    def parse_inspect(self, raw: str) -> ContainerInfo:
        item = parse_json_item(raw)              # domain/json_parsing.py
        ...

    def parse_list(self, raw: str) -> list[ContainerInfo]:
        data = parse_json_list(raw)              # domain/json_parsing.py
        ...

    def parse_prune(self, raw: str) -> PruneResult:
        return parse_prune_result(raw)           # domain/prune_parsing.py

    def is_not_found_error(self, stderr: str) -> bool:
        return matches_any_pattern(stderr, self._not_found_patterns)  # domain/error_matching.py
```

Image parsers additionally implement `is_auth_error`:
```python
class DockerImageParser(ImageParser):
    _auth_error_patterns = ("pull access denied", "unauthorized", "authentication required")
    ...
    def is_auth_error(self, stderr: str) -> bool:
        return matches_any_pattern(stderr, self._auth_error_patterns)  # domain/error_matching.py
```

**Boilerplate cost per parser:**
- `is_not_found_error`: 3 lines (one domain helper call)
- `parse_prune`: 3 lines (one domain helper call)
- `is_auth_error` (image parsers only): 3 lines
- Total: ~6-9 extra lines per parser × 8 parsers = ~48-72 lines total

This is the price of keeping ports pure. Without this, `BaseCliParser` would need to live in `ports/` with concrete methods.

**No `BaseCliParser` means:** The `_coerce_size` and `_safe_int` module-level functions from `adapters/parser/base.py` move to `domain/size_parsing.py`. Parsers import them directly:
```python
from oci_runtime.domain.size_parsing import coerce_size, safe_int
```

**No `BaseCliParser` means:** The scalar guard fix (A2) is implemented in the domain function `parse_json_item()`, not on any base class. Every parser that calls `parse_json_item()` automatically gets the fix.

### D8. Manager decomposition — DI of `ResultChecker` + `ListExecutor`, no `CliBaseManager`

Each concrete manager stops inheriting from `CliBaseManager`. Instead, it implements the port ABC directly and receives `ResultChecker` and `ListExecutor` via constructor injection.

**Before (current):**
```python
class CliContainerManager(CliBaseManager[ContainerParser], ContainerManager):
    _not_found_error = ContainerNotFoundError
    _generic_error = ContainerRuntimeError
    def __init__(self, transport, parser, caps, streaming, tty_detector, ...):
        super().__init__(transport, parser, caps)
        ...
    def run(self, config):
        ...
        self._check_result(result, cmd, ...)   # inherited from CliBaseManager
    def list(self, show_all, filters):
        ... copy-pasted boilerplate ...
```

**After:**
```python
class CliContainerManager(ContainerManager):
    def __init__(
        self,
        transport: Transport,
        parser: ContainerParser,
        caps: RuntimeCapabilities,
        streaming: StreamingTransport,
        tty_detector: TtyDetector,
        *,
        pty_transport: PtyTransport,
        cancellation_factory: Callable[[], CancellationToken],
        output_stream: OutputStream | None = None,
        result_checker: ResultChecker,            # NEW — injected
        list_executor: ListExecutor[ContainerInfo],  # NEW — injected
    ):
        self._transport = transport
        self._parser = parser
        self._caps = caps
        self._streaming = streaming
        self._tty_detector = tty_detector
        self._pty_transport = pty_transport
        self._cancellation_factory = cancellation_factory
        self._output_stream = output_stream
        self._result_checker = result_checker
        self._list_executor = list_executor

    def run(self, config):
        ...
        self._result_checker.check(
            result, cmd,
            operation="run container",
            entity=config.image,
            not_found_error=ImageNotFoundError,  # override: this is an image check
        )

    def list(self, show_all=False, filters=None) -> list[ContainerInfo]:
        return self._list_executor.execute_list(
            ["container", "list"], "containers",
            show_all=show_all, filters=filters,
        )

    def exec_container(self, container, command, ...):
        # Intentional bypass of standard check — returns exit code, not raise
        result = self._transport.execute(cmd, timeout=timeout)
        stderr_str = safe_decode(result.stderr)
        if result.returncode != 0 and self._parser.is_not_found_error(stderr_str):
            raise ContainerNotFoundError(container)
        return ExecResult(returncode=result.returncode, ...)
```

**Boilerplate cost per manager:**
- Each manager now declares `_result_checker` and `_list_executor` as constructor params and stores them (~4 lines each).
- `list()` becomes 2 lines (was ~9 lines copy-pasted).
- No explicit `_not_found_error`/`_generic_error` class attributes (they are now on the `CliResultChecker` instance).
- Total: ~10 extra lines of wiring per manager to eliminate the base class dependency.

**Key consequence:** The `_not_found_error` required-class-attribute contract (ARCHITECTURE.md L175, D8 in proposal) is now enforced via the `ResultChecker` constructor — it's impossible to instantiate a `CliResultChecker` without providing `not_found_error`. The regression test (D8 in v3 plan) still applies but checks `CliResultChecker` construction instead of class attribute presence.

### D9. Provider decomposition — DI of parser classes, no `BaseCliRuntimeProvider`

Each provider implements `RuntimeProvider` directly. The factory injects parser classes via the constructor.

**Before:**
```python
class DockerRuntimeProvider(BaseCliRuntimeProvider):
    _kind = RuntimeKind.DOCKER
    _container_parser_cls = DockerContainerParser
    ...
```

**After:**
```python
# adapters/provider/docker.py
class DockerRuntimeProvider(RuntimeProvider):
    def __init__(
        self,
        *,
        container_parser_cls: type[ContainerParser],
        image_parser_cls: type[ImageParser],
        volume_parser_cls: type[VolumeParser],
        network_parser_cls: type[NetworkParser],
        caps: RuntimeCapabilities,
    ):
        self._container_parser_cls = container_parser_cls
        self._image_parser_cls = image_parser_cls
        self._volume_parser_cls = volume_parser_cls
        self._network_parser_cls = network_parser_cls
        self._caps = caps

    @property
    def kind(self) -> RuntimeKind:
        return RuntimeKind.DOCKER

    def capabilities(self) -> RuntimeCapabilities:
        return self._caps

    def create_parsers(self) -> Parsers:
        return Parsers(
            container_parser=self._container_parser_cls(),
            image_parser=self._image_parser_cls(),
            volume_parser=self._volume_parser_cls(),
            network_parser=self._network_parser_cls(),
        )
```

The factory wires the provider with concrete classes:

```python
# factory.py
def _default_providers():
    from oci_runtime.adapters.parser.docker import (
        DockerContainerParser, DockerImageParser,
        DockerVolumeParser, DockerNetworkParser,
    )
    return {
        RuntimeKind.DOCKER: DockerRuntimeProvider(
            container_parser_cls=DockerContainerParser,
            image_parser_cls=DockerImageParser,
            volume_parser_cls=DockerVolumeParser,
            network_parser_cls=DockerNetworkParser,
            caps=_DOCKER_CAPABILITIES,
        ),
        ...
    }
```

The capability constants (`_DOCKER_CAPABILITIES`, `_PODMAN_CAPABILITIES`) are defined in each provider module directly.

**Boilerplate cost per provider:** ~15 lines instead of ~5 with the base class. Two providers = ~30 lines total. The tradeoff: zero adapter→adapter imports in provider files.

### D10. Factory wiring — full DI graph

`RuntimeFactory.create()` becomes the single place where every adapter is wired. The factory creates:

1. Per-provider singletons (unchanged)
2. Per-engine-instance: transport, streaming transport, pty transport, resolvers
3. Per-manager: `ResultChecker` instance, `ListExecutor[T]` instance, then the manager itself

```python
def create(self, preference: RuntimePreference) -> ContainerEngine:
    binary = preference.binary
    binary_resolver = self._cfg.binary_resolver_factory()
    transport = self._cfg.transport_factory(binary, binary_resolver=binary_resolver)
    streaming_transport = self._cfg.streaming_transport_factory(
        binary, binary_resolver=binary_resolver
    )
    pty_transport = self._cfg.pty_transport_factory(binary_resolver)
    provider = self._providers[preference.kind]
    caps = provider.capabilities()
    parsers = provider.create_parsers()

    # Per-manager ResultCheckers
    container_checker = CliResultChecker(
        generic_error=ContainerRuntimeError,
        not_found_error=ContainerNotFoundError,
        is_not_found=parsers.container_parser.is_not_found_error,
    )
    image_checker = CliResultChecker(
        generic_error=ImageRuntimeError,
        not_found_error=ImageNotFoundError,
        is_not_found=parsers.image_parser.is_not_found_error,
        auth_error=ImagePullAccessDeniedError,
        is_auth=parsers.image_parser.is_auth_error,
    )
    volume_checker = CliResultChecker(
        generic_error=VolumeRuntimeError,
        not_found_error=VolumeNotFoundError,
        is_not_found=parsers.volume_parser.is_not_found_error,
    )
    network_checker = CliResultChecker(
        generic_error=NetworkRuntimeError,
        not_found_error=NetworkNotFoundError,
        is_not_found=parsers.network_parser.is_not_found_error,
    )

    # Per-manager ListExecutors
    container_list_executor = CliListExecutor[ContainerInfo](
        transport, caps, container_checker,
        parse_list=parsers.container_parser.parse_list,
    )
    image_list_executor = CliListExecutor[ImageInfo](
        transport, caps, image_checker,
        parse_list=parsers.image_parser.parse_list,
    )
    volume_list_executor = CliListExecutor[VolumeInfo](
        transport, caps, volume_checker,
        parse_list=parsers.volume_parser.parse_list,
    )
    network_list_executor = CliListExecutor[NetworkInfo](
        transport, caps, network_checker,
        parse_list=parsers.network_parser.parse_list,
    )

    # Managers
    image_manager = CliImageManager(
        transport, parsers.image_parser, caps,
        result_checker=image_checker,
        list_executor=image_list_executor,
    )
    container_manager = CliContainerManager(
        transport, parsers.container_parser, caps,
        streaming=streaming_transport,
        tty_detector=self._cfg.tty_detector_factory(),
        pty_transport=pty_transport,
        cancellation_factory=self._cfg.cancellation_factory,
        output_stream=self._cfg.output_stream_factory(),
        result_checker=container_checker,
        list_executor=container_list_executor,
    )
    volume_manager = CliVolumeManager(
        transport, parsers.volume_parser, caps,
        result_checker=volume_checker,
        list_executor=volume_list_executor,
    )
    network_manager = CliNetworkManager(
        transport, parsers.network_parser, caps,
        result_checker=network_checker,
        list_executor=network_list_executor,
    )

    return self._cfg.runtime_cls(
        transport=transport,
        image_manager=image_manager,
        container_manager=container_manager,
        volume_manager=volume_manager,
        network_manager=network_manager,
        caps=caps,
    )
```

`RuntimeFactoryConfig` gains two new factory fields:
```python
@dataclass(frozen=True)
class RuntimeFactoryConfig:
    ...existing fields...
    result_checker_factory: Callable[..., ResultChecker] | None = None
    list_executor_factory: Callable[..., ListExecutor] | None = None
```

Both default to their respective `Cli*` adapters via `_resolve_config`. Tests can inject `MagicMock(spec=ResultChecker)` to verify manager behavior without instantiated operations.

### D11. PortMapping.host_ip honored (A1) — unchanged from v3 plan

Same as v3 proposal: `_port_flag()` helper handles all 4 combinations. Parsers preserve the CLI truth (empty HostIp → `None`, explicit "0.0.0.0" → `"0.0.0.0"`). The implementation goes in `CliContainerManager.run()` directly (no base class to add it to).

### D12. version() error contract (A7) — unchanged from v3 plan

`CliRuntime.version()` raises `OciError` with full context on non-zero exit. Simple conditional in the engine facade.

### D13. Remaining audit bug fixes (A2, A3, A4, A5, A6, A8) — same fix, different location

| Finding | Fix | Where | Change from v3 plan |
|---------|-----|-------|---------------------|
| A2 | Scalar guard in `_parse_json_item` | `domain/json_parsing.py:parse_json_item()` | Same logic, different file |
| A3 | Strict `ProcessPipeReader.from_process()` | `adapters/_process_reader.py` | Unchanged |
| A4 | Auth error carries `command`/`exit_code`/`stderr` | `CliResultChecker.check()` | Now in adapter, not in a shared base |
| A5 | PTY raises `OciError`, not `ContainerRuntimeError` | `transport/pty.py` | Unchanged |
| A6 | `pull()` raises `ImageRuntimeError` with context | `CliImageManager.pull()` | Unchanged semantics |
| A8 | Delete `Managers` aggregate, update docs | `ports/aggregates.py`, ARCHITECTURE.md | Unchanged |

## Component Map

### New files (11)

| File | Type | Contents |
|------|------|----------|
| `domain/build_tar.py` | domain | `create_build_tar`, `_validate_tar_path` |
| `domain/size_parsing.py` | domain | `parse_size_to_bytes`, `coerce_size`, `safe_int` |
| `domain/json_parsing.py` | domain | `parse_json_item`, `parse_json_list` |
| `domain/error_matching.py` | domain | `matches_any_pattern` |
| `domain/prune_parsing.py` | domain | `parse_prune_result` |
| `domain/list_command.py` | domain | `build_list_command` |
| `domain/encoding.py` | domain | `safe_decode` |
| `domain/result_checking.py` | domain | `check_cli_result` (pure function version of ResultChecker logic, used when a port is too heavy) |
| `ports/result_checker.py` | port | `ResultChecker` ABC (1 abstract method) |
| `ports/list_executor.py` | port | `ListExecutor[T]` ABC (1 abstract method, `Generic[T]`) |
| `adapters/helpers/result_checker.py` | adapter | `CliResultChecker` |
| `adapters/helpers/list_executor.py` | adapter | `CliListExecutor[T]` |

### Removed files (4)

| File | Reason |
|------|--------|
| `adapters/parser/base.py` | BaseCliParser deleted; logic moved to domain helpers |
| `adapters/managers/base.py` | CliBaseManager deleted; replaced by ResultChecker/ListExecutor ports |
| `adapters/provider/_base.py` | BaseCliRuntimeProvider deleted; providers implement RuntimeProvider directly |
| `ports/aggregates.py` (`Managers` only) | Dead code (A8) |

### Modified files (16+)

| File | Change |
|------|--------|
| `adapters/parser/docker.py` | Remove `BaseCliParser` inheritance; call domain helpers |
| `adapters/parser/podman.py` | Same |
| `adapters/managers/container.py` | Remove `CliBaseManager` inheritance; accept `ResultChecker` + `ListExecutor`; use DI |
| `adapters/managers/image.py` | Same |
| `adapters/managers/volume.py` | Same |
| `adapters/managers/network.py` | Same |
| `adapters/provider/docker.py` | Remove `BaseCliRuntimeProvider`; implement `RuntimeProvider` directly; accept parser classes via constructor |
| `adapters/provider/podman.py` | Same |
| `adapters/transport/cli.py` | Accept `pipe_reader_factory`; import `compose_tokens` from `ports.cancellation` |
| `adapters/transport/streaming.py` | Same |
| `adapters/transport/pty.py` | Accept `pipe_reader_factory`; drop lazy `StdoutBufferStream`; raise `OciError` for empty command |
| `adapters/_process_reader.py` | Strict `from_process()` (A3) |
| `adapters/_cancellation.py` | `CompositeCancellationToken` + `compose_tokens` removed (moved to ports) |
| `ports/cancellation.py` | Add `CompositeCancellationToken` + `compose_tokens` |
| `ports/__init__.py` | Export new ports; stop exporting `Managers` |
| `domain/__init__.py` | Export new domain modules |
| `factory.py` | Wire `ResultChecker` and `ListExecutor` instances per manager |
| `oci_runtime/__init__.py` | Add `ProviderNotRegisteredError`; stop exporting `Managers` |

## Migration Plan

Seven phases, each leaving the test suite green:

1. **Phase T1 — Domain scaffolding** (additive, no behavior change): Create 7 domain modules + 2 port modules + 2 helper ports. Add re-export shims in old adapter locations so existing imports still work. No behavioral change. Test suite green.

2. **Phase T2 — Rewire parsers**: Stop inheriting from `BaseCliParser`. Each parser implements port ABC directly and calls domain helpers. Delete `adapters/parser/base.py`. Test suite green.

3. **Phase T3 — Rewire managers**: Stop inheriting from `CliBaseManager`. Each manager accepts `ResultChecker` + `ListExecutor` via constructor injection. Factory updated to wire them. Delete `adapters/managers/base.py`. Test suite green.

4. **Phase T4 — Rewire providers**: Stop inheriting from `BaseCliRuntimeProvider`. Each provider implements `RuntimeProvider` directly, receives parser classes from factory. Delete `adapters/provider/_base.py`. Test suite green + architecture linter enforces `adapters → {domain, ports}`.

5. **Phase T5 — Audit bug fixes** (A1, A2, A3, A4, A5, A6, A7, A8): One commit per bug, each with a regression test. Test suite green after each commit.

6. **Phase T6 — Test quality + doc drift cleanup** (D, E, C series): Test corrections, dead code removal, doc alignment. Final suite green.

7. **Phase T7 — Conformance + integration**: Run against real docker/podman fixtures. Optional validation phase.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| **R1**: D7/D8/D9 boilerplate adds ~48-72 parser lines + ~40 manager lines + ~30 provider lines = ~120-140 lines of simple delegation code. | Each line is trivial (domain call or constructor store). Less risk than shared bases with complex inheritance chains. |
| **R2**: `ListExecutor[ContainerInfo]` generic type parameter is erased at runtime. Static checkers (mypy/pyright) enforce correctness; runtime relies on the `parse_list` callable returning the right type. | `parse_list` is sourced from the same parser instance used by the manager, ensuring type consistency. Integration tests verify round-trip correctness. |
| **R3**: `ResultChecker` shares instance between manager and `ListExecutor`. If the manager modifies checker state, `ListExecutor` sees it. | `CliResultChecker` is stateless — all configuration is constructor-injected and read-only. `check()` is a pure function in mutable disguise (reads fields, raises or returns). |
| **R4**: `exec_container()` accesses `self._parser.is_not_found_error()` directly (not through `ResultChecker`). This is an adapter→port call, which is allowed. | The intentional bypass is documented in code. `exec_container` has different semantics (returns exit codes) and should not go through the standard check. |
| **R5**: Eight concrete parsers need the same `is_not_found_error` / `parse_prune` boilerplate. | Each is 3 lines calling a domain helper. Far less risk than the 4× copy-pasted list methods (C1) that motivated this refactor. |
