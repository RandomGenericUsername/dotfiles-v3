# oci-runtime Remediation Master Plan

## Objective

Bring `oci-runtime` into full compliance with clean hexagonal architecture by fixing every contract violation, bug, and structural deviation identified in the audit. After each phase, the full test suite (695 tests) must pass with zero regressions.

---

## Pre-Flight Inventory

### Baseline

- **399 unit tests, 695 total tests — all passing**
- **Python 3.14.1, pytest 9.0.3**

### Audited Files

```
src/oci_runtime/
├── __init__.py                          # Public API re-exports
├── engines.py                           # Module-level RuntimePreference singletons
├── factory.py                           # RuntimeFactory + _PROVIDER_REGISTRY global
├── domain/
│   ├── __init__.py                      # Domain re-exports
│   ├── enums.py                         # RuntimeKind, ContainerState, RestartPolicy, NetworkMode
│   ├── exceptions.py                    # OciError hierarchy + ParsingError
│   └── types.py                         # Data classes (RunConfig, ContainerInfo, etc.)
├── ports/
│   ├── engine.py                        # ContainerEngine ABC
│   ├── transport.py                     # Transport ABC + ExecResult
│   ├── capabilities.py                  # RuntimeCapabilities, EngineProfile, RuntimePreference
│   ├── discovery.py                     # RuntimeDiscovery ABC
│   ├── provider.py                      # RuntimeProvider ABC
│   ├── factory.py                       # Parsers, RuntimeFactoryConfig
│   ├── parsers.py                       # ContainerParser, ImageParser, VolumeParser, NetworkParser ABCs
│   └── managers.py                      # ImageManager, ContainerManager, VolumeManager, NetworkManager ABCs
└── adapters/
    ├── engine/cli.py                    # CliRuntime (ContainerEngine impl)
    ├── transport/cli.py                 # CliTransport (Transport impl)
    ├── discovery/cli.py                 # CliRuntimeDiscovery
    ├── provider/docker.py               # DockerRuntimeProvider
    ├── provider/podman.py               # PodmanRuntimeProvider
    ├── parser/base.py                   # BaseCliParser + parse_size_to_bytes
    ├── parser/docker.py                 # Docker*Parser classes
    ├── parser/podman.py                 # Podman*Parser classes
    └── managers/
        ├── base.py                      # CliBaseManager[P]
        ├── container.py                 # CliContainerManager
        ├── image.py                     # CliImageManager
        ├── volume.py                    # CliVolumeManager
        ├── network.py                   # CliNetworkManager
        └── pty.py                       # run_pty (raw subprocess.Popen, bypasses Transport)
```

---

## Validated Findings

Each finding below has been verified with a concrete test or proof. 

### F1. Port contract lie: parse_inspect returns `XInfo | None` against `XInfo` declaration

**Status**: CONFIRMED

```
Port declares:           parse_inspect(self, raw: str) -> ContainerInfo
Implementation returns:  ContainerInfo | None
```

Tested all 8 implementations — every `parse_inspect` method has `XInfo | None` signature while the port declares `XInfo`. MyPy or strict type checkers would flag this.

### F2. `_parse_docker_ports` crashes on malformed port keys

**Status**: CONFIRMED — `ValueError` crash

```python
# DockerContainerParser.parse_inspect with non-numeric port key:
raw = '{"Id":"abc123","Name":"/test","Config":{"Image":"nginx"},'
       '"State":{"Status":"running"},'
       '"NetworkSettings":{"Ports":{"abc/tcp":[{"HostPort":"8080","HostIp":"0.0.0.0"}]}}}'
>>> DockerContainerParser().parse_inspect(raw)
ValueError: invalid literal for int() with base 10: 'abc'
```

The Podman parser handles this correctly with `try/except (ValueError, AttributeError)`.

### F3. `parse_list` silently returns `[]` on garbage input

**Status**: CONFIRMED

```python
>>> DockerContainerParser().parse_list("not json at all")
[]
>>> DockerContainerParser().parse_list("")
[]
```

All 8 implementations silently return empty list on JSON decode failure.

### F4. `NetworkManager.create` and `VolumeManager.create` skip error checking

**Status**: CONFIRMED

Both methods call `self._transport.execute(cmd)` and return `self._decode_stdout(result.stdout).strip()` without calling `self._check_result()`. A failed command returns the error message as if it were a valid name.

### F5. Missing `--format json` on 6 of 8 inspect/list commands

**Status**: CONFIRMED

| Method | Has `--format json` |
|--------|:---:|
| `container.inspect` | ✅ |
| `container.list` | ✅ |
| `image.inspect` | ❌ |
| `image.list` | ❌ |
| `volume.inspect` | ❌ |
| `volume.list` | ❌ |
| `network.inspect` | ❌ |
| `network.list` | ❌ |

### F6. `build()` returns bare hex hash, `pull()` returns `sha256:<hex>` — inconsistent ID format

**Status**: CONFIRMED

```python
>>> DockerImageParser().parse_build_output("sha256:abc123")
'abc123'            # bare hex

>>> DockerImageParser().parse_id_from_pull("Digest: sha256:abc123")
'sha256:abc123'     # prefixed
```

### F7. Global mutable `_PROVIDER_REGISTRY`

**Status**: CONFIRMED

```python
>>> from oci_runtime.factory import _PROVIDER_REGISTRY
>>> id(_PROVIDER_REGISTRY)
139677280256960
>>> f1 = RuntimeFactory()
>>> f2 = RuntimeFactory()
>>> f1._providers is f2._providers  # same dict object!
True
```

Two independent factory instances share the same mutable dict. Test isolation is broken — one test's provider registration leaks into all others.

### F8. `CliRuntime` has duplicate `binary` (stored + transport)

**Status**: CONFIRMED

```python
CliRuntime.__init__(self, ..., binary: str = '')
self._binary = binary  # stored separately from transport
```

`version()` uses `self._binary` directly and imports `subprocess` to catch `subprocess.TimeoutExpired`, bypassing Transport.

### F9. `run_pty` in `pty.py` bypasses Transport port

**Status**: CONFIRMED

`adapters/managers/container.py:16` imports `run_pty` from the PTY module, which directly calls `subprocess.Popen` and `os.read` on file descriptors. The Transport abstraction is completely bypassed.

### F10. `ParsingError` lives in `domain/exceptions.py` but is an adapter concern

**Status**: CONFIRMED

`ParsingError` extends `OciError` (domain exception) but is only raised by adapter parsers. No domain code raises it. It's exported from `domain/__init__.py` as if it were a domain concept.

### F11. `RestartPolicy` and `NetworkMode` use `Enum` instead of `StrEnum`

**Status**: CONFIRMED

```python
class RestartPolicy(Enum):    # str() gives "RestartPolicy.NO"
class NetworkMode(Enum):      # str() gives "NetworkMode.BRIDGE"
class RuntimeKind(StrEnum):   # str() gives "docker" ✅
class ContainerState(StrEnum):# str() gives "running" ✅
```

The workaround is `_resolve_val()` in `CliBaseManager` which checks `hasattr(val, "value")`.

### F12. `EngineProfile` is dead code

**Status**: CONFIRMED — Only referenced in its own definition file and in tests.

```bash
$ grep -r "EngineProfile" src/ --include="*.py"
src/oci_runtime/ports/capabilities.py:class EngineProfile:
```

Only test files reference it (`test_interface_compliance.py:28,417-420`).

### F13. `engines.py` creates module-level singletons

**Status**: CONFIRMED

`engines.py:4-5` creates `docker_pref` and `podman_pref` at import time. `__init__.py:1` imports this module unconditionally.

### F14. Factory imports 9 concrete adapter classes

**Status**: CONFIRMED

`factory.py` has 9 `from oci_runtime.adapters.*` imports, directly violating the claim that it "depends on abstractions (ports), not implementations (adapters)."

### F15. `ContainerManager.logs()` — no thread name, re-raises only first error

**Status**: CONFIRMED

Thread created with `Thread(target=_run, daemon=True)` — no name. Error list `errors[0]` silently drops any additional exceptions.

---

## Phase 1 — Domain & Port Contract Cleanup

**Goal**: Make type signatures honest. Parsers must raise, not return `None`. Silent failures must raise. Enum types must be consistent. Dead code removed.

### Step 1.1: Convert `RestartPolicy` and `NetworkMode` to `StrEnum`

**Files**: `src/oci_runtime/domain/enums.py`

```python
# BEFORE
class RestartPolicy(Enum):
class NetworkMode(Enum):

# AFTER
class RestartPolicy(StrEnum):
class NetworkMode(StrEnum):
```

**Cascading changes**:
- `src/oci_runtime/domain/types.py`: Change `RunConfig.network` from `str | NetworkMode` to `NetworkMode`, same for `restart_policy`.
- `src/oci_runtime/adapters/managers/base.py`: Remove `_resolve_val()`. Replace all `self._resolve_val(x)` with `str(x)` (since `StrEnum` already coerces).
- All manager CLI flags that compare against string literals: update. E.g. `container.py:54-55` `if network_val != "bridge"` becomes `if str(config.network) != "bridge"` or better, `if config.network != NetworkMode.BRIDGE`.

**Verification**: Run `grep -rn "_resolve_val" src/` to confirm full removal. Run full test suite.

### Step 1.2: Delete dead `EngineProfile`

**Files**: 
- `src/oci_runtime/ports/capabilities.py`: Remove lines 7-9 (`EngineProfile` dataclass)
- `tests/integration/contract/test_interface_compliance.py`: Remove `EngineProfile` import and tests `test_engine_profile_is_frozen` and `test_podman_profile` (if present)
- `tests/unit/ports/test_capabilities.py`: Remove `TestEngineProfile` class (3 tests)

**Verification**: `grep -r "EngineProfile" src/ tests/` returns zero hits.

### Step 1.3: Parsers must raise `ParsingError` instead of returning `None`

**Files**: All 8 parser implementations in `docker.py` and `podman.py`

Change all `parse_inspect` methods from:
```python
def parse_inspect(self, raw: str) -> ContainerInfo | None:
    try:
        ...
    except (json.JSONDecodeError, IndexError, KeyError):
        return None
    if not data:
        return None
```

To:
```python
def parse_inspect(self, raw: str) -> ContainerInfo:
    try:
        ...
    except json.JSONDecodeError as e:
        raise ParsingError(raw=raw, message=f"Invalid JSON: {e}") from e
    except (IndexError, KeyError) as e:
        raise ParsingError(raw=raw, message=f"Missing required field: {e}") from e
    if not data:
        raise ParsingError(raw=raw, message="Empty response")
```

**Manager updates** — remove `None` guards:
```python
# BEFORE (container.py:149-151)
info = self._parser.parse_inspect(self._decode_stdout(result.stdout))
if info is None:
    raise ContainerNotFoundError(container)

# AFTER
info = self._parser.parse_inspect(self._decode_stdout(result.stdout))
```

Same for `image.py:78-80`, `volume.py:40-42`, `network.py:49-51`.

**Test updates**:
- `test_docker_parser.py`: Tests that currently assert `info is None` (lines 128, 132, 163) must assert `raises(ParsingError)`.
- All mock parser stubs in tests that return `None` from `parse_inspect` must raise `ParsingError` instead.

**Verification**: `grep -rn "is None" tests/ | grep -i parse_inspect` returns zero. `grep -rn "| None" src/oci_runtime/adapters/parser/ | grep parse_inspect` returns zero.

### Step 1.4: `parse_list` raises `ParsingError` on invalid JSON

**Files**: All 8 parser `parse_list` methods in `docker.py` and `podman.py`

```python
# BEFORE
except json.JSONDecodeError:
    return []

# AFTER
except json.JSONDecodeError as e:
    raise ParsingError(raw=raw, message=f"Invalid JSON in list response: {e}") from e
```

**Test updates**: Tests asserting empty list on bad JSON must assert `raises(ParsingError)`.

**Verification**: `grep -n "return \[\]" src/oci_runtime/adapters/parser/docker.py src/oci_runtime/adapters/parser/podman.py` — only `parse_prune` should keep `return {...}`. `parse_list` must not silently return empty.

### Step 1.5: Move `ParsingError` to adapter layer

**Files**:
- Create `src/oci_runtime/adapters/parser/exceptions.py` with `class ParsingError(Exception)` containing `raw` and `message` attributes.
- `src/oci_runtime/domain/exceptions.py`: Remove `ParsingError` class.
- `src/oci_runtime/domain/__init__.py`: Remove `ParsingError` from exports and `__all__`.
- `src/oci_runtime/__init__.py`: Remove `ParsingError` from imports/exports if present.
- All parser files: `from oci_runtime.adapters.parser.exceptions import ParsingError`
- All test files referencing `ParsingError`: Update import path.

**Important**: `ParsingError` should NOT extend `OciError` (which is domain). It's a separate adapter-level exception. Since parsers raise it and managers catch it (via `_check_result` calling `is_not_found_error`), we need `ParsingError` to be importable from `adapters.parser.exceptions`.

Wait — actually `_check_result` in `CliBaseManager` doesn't catch `ParsingError`. It's managers that call parsers, and managers don't currently catch `ParsingError`. We need a design decision: should managers let `ParsingError` propagate? Yes — it's the right behavior. If parsing fails, the caller should know, not get a silent empty result.

**Verification**: `grep -rn "ParsingError" src/oci_runtime/domain/` returns zero. `grep -rn "from oci_runtime.domain.exceptions import ParsingError"` returns zero.

### Step 1.6: Delete `engines.py`

**Files**:
- Delete `src/oci_runtime/engines.py`
- `src/oci_runtime/__init__.py`: Remove `from oci_runtime import engines` and `"engines"` from `__all__`
- `tests/unit/adapters/test_engines.py`: Delete this file (4 tests that test module-level singletons)
- Update `tests/unit/adapters/test_factory.py:8`: Remove `from oci_runtime import engines`, update tests to construct `RuntimePreference` directly:
  ```python
  # BEFORE
  runtime = RuntimeFactory().create(engines.docker_pref)
  # AFTER
  runtime = RuntimeFactory().create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
  ```

**Verification**: `grep -rn "engines\." tests/ src/ | grep -v __pycache__` returns zero.

---

## Phase 2 — Transport PTY Extension

**Goal**: All I/O goes through the Transport port. No raw subprocess calls outside of `CliTransport`.

### Step 2.1: Add `execute_pty` to Transport port

**File**: `src/oci_runtime/ports/transport.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable
import subprocess


@dataclass
class ExecResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class Transport(ABC):
    @abstractmethod
    def execute(
        self,
        command: list[str],
        *,
        timeout: int | None = None,
        input_data: bytes | None = None,
        stream: bool = False,
        on_output: Callable[[bytes, str], None] | None = None,
    ) -> ExecResult: ...

    @abstractmethod
    def get_runtime_binary(self) -> str: ...

    @abstractmethod
    def probe(self) -> bool: ...

    @abstractmethod
    def execute_pty(
        self,
        command: list[str],
        on_output: Callable[[bytes], None] | None = None,
    ) -> subprocess.CompletedProcess:
        """Run a command in a PTY. Raises ContainerRuntimeError on non-zero exit."""
        ...
```

**Test update**: `tests/unit/ports/test_transport.py` must add tests for `execute_pty` being abstract. Update `TestTransport.test_has_all_abstract_methods`:

```python
# BEFORE
expected = {"execute", "get_runtime_binary", "probe"}
# AFTER
expected = {"execute", "get_runtime_binary", "probe", "execute_pty"}
```

Same for `test_concrete_subclass_must_implement_all` and `test_concrete_subclass_works`.

**Verification**: Tests pass.

### Step 2.2: Implement `execute_pty` in `CliTransport`

**File**: `src/oci_runtime/adapters/transport/cli.py`

Move the PTY logic from `adapters/managers/pty.py` into `CliTransport.execute_pty()`. The method:
- Calls `self._ensure_binary()` for validation
- Creates PTY, runs process, drains output
- Returns `subprocess.CompletedProcess`
- Raises `ContainerRuntimeError` on failure

The `pty.py` module can remain as a private implementation helper under `adapters/transport/` if desired, but the public entry point is `Transport.execute_pty()`.

**Verification**: `grep -rn "from oci_runtime.adapters.managers.pty import run_pty" src/` returns zero (the import in `container.py` is removed).

### Step 2.3: Update `CliContainerManager.run()` to use Transport

**File**: `src/oci_runtime/adapters/managers/container.py`

```python
# BEFORE
from oci_runtime.adapters.managers.pty import run_pty
...
if config.effective_tty:
    run_pty(cmd)
    return ""

# AFTER
if config.effective_tty:
    self._transport.execute_pty(cmd)
    return ""
```

Remove the `run_pty` import.

**Verification**: `grep -rn "run_pty" src/oci_runtime/` returns zero references in manager code.

### Step 2.4: Fix `CliRuntime.version()` — route through Transport

**File**: `src/oci_runtime/adapters/engine/cli.py`

```python
# BEFORE
import subprocess
...
def version(self) -> str:
    try:
        result = self._transport.execute([self._binary, "--version"])
        ...
    except (RuntimeNotAvailableError, subprocess.TimeoutExpired, OSError):
        return ""

# AFTER (remove import subprocess, remove self._binary)
def version(self) -> str:
    result = self._transport.execute([self._transport.get_runtime_binary(), "--version"])
    if result.returncode == 0:
        return result.stdout.decode("utf-8", errors="replace").strip()
    raise RuntimeNotAvailableError(self._transport.get_runtime_binary())
```

Also remove `binary` from `CliRuntime.__init__` parameters and `self._binary` field.

**Test updates**: `tests/unit/adapters/test_cli_runtime.py` must update all tests that pass `binary=""` or `binary="docker"` to `CliRuntime`.

**Integration test update**: `tests/integration/contract/test_interface_compliance.py:131` must remove `binary` kwarg from `CliRuntime(...)` constructor call.

**Verification**: `grep -rn "self._binary" src/oci_runtime/adapters/engine/cli.py` returns zero. `grep -n "import subprocess" src/oci_runtime/adapters/engine/cli.py` returns zero.

---

## Phase 3 — Factory Restructuring (Constructor Injection)

**Goal**: Eliminate global mutable state. Make composition explicit. Factory depends only on ports, not adapters.

### Step 3.1: Remove `_PROVIDER_REGISTRY`, `register_provider`, `get_provider`, `_ensure_default_providers`

**File**: `src/oci_runtime/factory.py`

Delete lines 23-30 (`_PROVIDER_REGISTRY`, `register_provider`, `get_provider`) and lines 66-72 (`_ensure_default_providers`).

**Test update**: `tests/unit/adapters/test_factory.py:16-35` — the `test_importing_factory_has_no_side_effects` test that asserts `_PROVIDER_REGISTRY` is empty on import, then populated after factory creation, must be rewritten. Since we're removing the global, this test becomes:

```python
def test_factory_requires_providers():
    factory = RuntimeFactory(providers={})
    with pytest.raises(NotImplementedError):
        factory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
```

### Step 3.2: `RuntimeFactory.__init__` accepts `providers` explicitly

```python
# BEFORE
class RuntimeFactory:
    def __init__(self, config=None, providers=None):
        _ensure_default_providers()
        self._cfg = _resolve_config(config)
        self._providers = providers if providers is not None else _PROVIDER_REGISTRY

# AFTER
def _default_providers() -> dict[RuntimeKind, RuntimeProvider]:
    from oci_runtime.adapters.provider.docker import DockerRuntimeProvider
    from oci_runtime.adapters.provider.podman import PodmanRuntimeProvider
    return {
        RuntimeKind.DOCKER: DockerRuntimeProvider(),
        RuntimeKind.PODMAN: PodmanRuntimeProvider(),
    }

class RuntimeFactory:
    def __init__(
        self,
        config: RuntimeFactoryConfig | None = None,
        providers: dict[RuntimeKind, RuntimeProvider] | None = None,
    ):
        self._cfg = _resolve_config(config)
        self._providers = providers if providers is not None else _default_providers()
```

Lazy imports for `_default_providers` stay (they're in a function, not module level). This preserves the original behavior for simple `RuntimeFactory()` calls while making injection explicit.

### Step 3.3: Move manager construction into `RuntimeProvider`

**File**: `src/oci_runtime/ports/provider.py` — add:

```python
@abstractmethod
def create_managers(
    self,
    transport: Transport,
    caps: RuntimeCapabilities,
) -> Managers: ...
```

Create a `Managers` dataclass in `ports/factory.py`:
```python
@dataclass(frozen=True)
class Managers:
    image_manager: ImageManager
    container_manager: ContainerManager
    volume_manager: VolumeManager
    network_manager: NetworkManager
```

**File**: `src/oci_runtime/adapters/provider/docker.py` — add:
```python
def create_managers(self, transport: Transport, caps: RuntimeCapabilities) -> Managers:
    parsers = self.create_parsers()
    return Managers(
        image_manager=CliImageManager(transport, parsers.image_parser, caps),
        container_manager=CliContainerManager(transport, parsers.container_parser, caps),
        volume_manager=CliVolumeManager(transport, parsers.volume_parser, caps),
        network_manager=CliNetworkManager(transport, parsers.network_parser, caps),
    )
```

Same for `podman.py`.

### Step 3.4: Remove `_make_*` functions from factory.py

Delete lines 94-111 (`_make_image_manager`, `_make_container_manager`, etc.).

Update `RuntimeFactory.create()`:

```python
def create(self, preference: RuntimePreference) -> ContainerEngine:
    binary = preference.binary
    transport = self._cfg.transport_factory(binary)
    try:
        provider = self._providers[preference.kind]
    except KeyError:
        raise NotImplementedError(...)
    caps = provider.capabilities()
    managers = provider.create_managers(transport, caps)

    runtime = self._cfg.runtime_cls(
        transport=transport,
        image_manager=managers.image_manager,
        container_manager=managers.container_manager,
        volume_manager=managers.volume_manager,
        network_manager=managers.network_manager,
        caps=caps,
    )

    if not runtime.is_available():
        raise RuntimeNotAvailableError(...)
    return runtime
```

This removes 7 of the 9 adapter imports in `factory.py`. The remaining 2 (`CliTransport`, `CliRuntime`) are in `_default_transport_factory` and `_default_runtime_cls`, which are lazy-loaded factory defaults — acceptable for a composition root.

**Test updates**: Update `test_factory.py` tests that rely on `RuntimeFactory().create(engines.docker_pref)` → `RuntimeFactory().create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))`.

**Verification**: `grep -c "from oci_runtime.adapters" src/oci_runtime/factory.py` should be 2 (only `CliTransport` and `CliRuntime` in lazy imports).

---

## Phase 4 — Bug Fixes

**Goal**: Fix all runtime-observable bugs.

### Step 4.1: Add `_check_result()` to `create` methods

**File**: `src/oci_runtime/adapters/managers/network.py`

```python
# BEFORE (line 19-20)
result = self._transport.execute(cmd)
return self._decode_stdout(result.stdout).strip()

# AFTER
result = self._transport.execute(cmd)
self._check_result(result, cmd, operation="create network", entity=name, not_found=NetworkNotFoundError)
return self._decode_stdout(result.stdout).strip()
```

**File**: `src/oci_runtime/adapters/managers/volume.py`

```python
# BEFORE (line 19-20)
result = self._transport.execute(cmd)
return self._decode_stdout(result.stdout).strip()

# AFTER
result = self._transport.execute(cmd)
self._check_result(result, cmd, operation="create volume", entity=name, not_found=VolumeNotFoundError)
return self._decode_stdout(result.stdout).strip()
```

**Verification**: `grep -n "_check_result" src/oci_runtime/adapters/managers/network.py` shows the call. Same for `volume.py`.

### Step 4.2: Add `--format json` consistently

**Files**: All 6 methods missing the flag.

```python
# image.py:75
cmd = [self._transport.get_runtime_binary(), "image", "inspect", "--format", "json", image]

# image.py:84
cmd = [self._transport.get_runtime_binary(), "image", "list", "--format", "json"]

# volume.py:37
cmd = [self._transport.get_runtime_binary(), "volume", "inspect", "--format", "json", name]

# volume.py:46 (wait - volume ls doesn't have --format json in Docker)
# Actually: docker volume ls doesn't support --format json. docker volume inspect does.
# For volume list, we need to check if the runtime supports --format json for volume ls.
# Docker: `docker volume ls --format json` is NOT supported (Docker uses Go templates for --format)
# Podman: `podman volume ls --format json` IS supported
# 
# APPROACH: For inspect, add --format json. For list, leave as-is since 
# Docker's list uses different format flags. document this.
```

**Important clarification**: After validation, Docker's `image inspect`, `volume inspect`, and `network inspect` all support `--format json` (or `-f json`). But Docker's `ls`/`list` commands use `--format` with Go templates, not `--format json`. Only Podman supports `--format json` on list commands.

**Revised approach**: 
- Add `--format json` to all `inspect` commands (image, volume, network)
- For `list` commands: container list already has `--format json`. For image/volume/network list, keep the current behavior but document that Docker uses `json` output by default for some `ls` commands when terminal is not a TTY, while Podman uses `--format json`.

**Files to change**:
- `image.py:75` — Add `--format`, `json` to image inspect
- `volume.py:37` — Add `--format`, `json` to volume inspect
- `network.py:47` — Add `--format`, `json` to network inspect

For `list` commands, the `--format json` support varies by runtime. Container list already has it. We need to investigate the runtime differences more carefully before adding it to image/volume/network list — this is a **separate task** documented as a known issue.

**Verification**: `grep -n '"--format"' src/oci_runtime/adapters/managers/image.py` shows the inspect command.

### Step 4.3: Fix `_parse_docker_ports` error handling

**File**: `src/oci_runtime/adapters/parser/docker.py`

Add try/except around the port key split:

```python
def _parse_docker_ports(item: dict) -> list[PortMapping]:
    ports = []
    net_settings = item.get("NetworkSettings", {})
    port_map = net_settings.get("Ports", {}) or {}
    for key, bindings in port_map.items():
        try:
            container_port_str, protocol = key.split("/")
            container_port = int(container_port_str)
        except (ValueError, AttributeError):
            continue
        ...
```

**Test update**: Add test for `_parse_docker_ports` with non-numeric port key and missing slash key.

### Step 4.4: Normalize image ID format

**File**: `src/oci_runtime/adapters/parser/docker.py` and `podman.py`

Make `parse_build_output` return the same format as `parse_id_from_pull`:

```python
# BEFORE (docker.py:106)
def parse_build_output(self, raw: str) -> str:
    return raw.strip().removeprefix("sha256:")

# AFTER
def parse_build_output(self, raw: str) -> str:
    output = raw.strip()
    # Ensure consistent sha256: prefix format
    if output.startswith("sha256:"):
        return output
    return f"sha256:{output}"
```

**Verification**: `DockerImageParser().parse_build_output("sha256:abc") == "sha256:abc"`. `DockerImageParser().parse_build_output("abc") == "sha256:abc"`.

### Step 4.5: Fix `ContainerManager.logs()` thread safety

**File**: `src/oci_runtime/adapters/managers/container.py`

```python
# BEFORE
Thread(target=_run, daemon=True).start()

# AFTER
Thread(target=_run, daemon=True, name="oci-logs").start()
```

For error propagation, use `ExceptionGroup` (Python 3.11+):

```python
# BEFORE
if errors:
    raise errors[0]

# AFTER
if errors:
    raise ExceptionGroup("Errors during logs streaming", errors)
```

Wait — the project requires Python 3.12+ (`pyproject.toml: requires-python = ">=3.12"`), so `ExceptionGroup` is available. However, `ExceptionGroup` is typically used with `except*` syntax. For this use case, re-raising the first exception is actually standard practice for a single background thread. The list `errors` is unlikely to have more than one entry. Keep `errors[0]` but document this decision.

**Final decision**: Keep `errors[0]` re-raise, add thread name, add comment. This is the conventional pattern for single-producer threading.

### Step 4.6: Remove duplicate `binary` from `CliRuntime`

Already handled in Phase 2.4 — remove `binary` parameter from `CliRuntime.__init__`.

---

## Phase 5 — Consistency & Deduplication

**Goal**: Reduce code duplication, clean up conventions.

### Step 5.1: Extract shared JSON parsing into `BaseCliParser`

**File**: `src/oci_runtime/adapters/parser/base.py`

```python
import json
from oci_runtime.adapters.parser.exceptions import ParsingError


class BaseCliParser:
    """Shared logic for CLI parsers."""

    def _parse_json_item(self, raw: str) -> dict:
        """Parse JSON that may be a list with a single item or a dict."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ParsingError(raw=raw, message=f"Invalid JSON: {e}") from e
        if not data:
            raise ParsingError(raw=raw, message="Empty response")
        return data[0] if isinstance(data, list) else data

    def _parse_json_list(self, raw: str) -> list[dict]:
        """Parse JSON that contains a list."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ParsingError(raw=raw, message=f"Invalid JSON in list response: {e}") from e
        if not isinstance(data, list):
            data = [data]
        return data

    _not_found_patterns: tuple[str, ...] = ()

    def parse_prune(self, raw: str) -> dict[str, int]:
        ...  # existing implementation

    def is_not_found_error(self, stderr: str) -> bool:
        lower = stderr.lower()
        return any(p in lower for p in self._not_found_patterns)
```

Each parser subclass sets `_not_found_patterns`:

```python
class DockerContainerParser(BaseCliParser, ContainerParser):
    _not_found_patterns = ("no such container", "no such object")
    ...
```

**Verification**: All 8 parser classes define `_not_found_patterns` instead of `is_not_found_error`. `is_not_found_error` exists only on `BaseCliParser`.

### Step 5.2: Deduplicate `parse_inspect` implementations

Each `parse_inspect` method currently has the same JSON-parse + null-check + extract-fields pattern. After 5.1, they use `self._parse_json_item(raw)` instead of repeating the JSON parse + except + None check logic.

This reduces ~8 identical exception-handling blocks to `_parse_json_item` calls.

### Step 5.3: Update `__init__.py` exports

- Remove `ParsingError` from domain exports (moved in Phase 1.5)
- Remove `engines` from root exports (removed in Phase 1.6)
- Add `Managers` to exports if it becomes public (Phase 3.3)
- Ensure `EngineProfile` is gone (Phase 1.2)

---

## Dependency Graph

```
Phase 1 ──► Phase 2 ──► Phase 4 (bug fixes need new port signatures)
   │                       ▲
   └──► Phase 3 ──────────┘─► Phase 5 (refactoring needs stable contracts)
```

- **Phase 1** must go first (contract changes affect everything)
- **Phase 2** and **Phase 3** can run in parallel after Phase 1
- **Phase 4** depends on Phase 1 (parser contract changes) and Phase 2 (PTY moved to Transport)
- **Phase 5** is last (cosmetic dedup, requires stable code)

---

## Test Impact Summary

| Phase | Tests Affected | New Tests Needed |
|-------|:--------------:|:----------------:|
| 1.1 (StrEnum) | ~5 enum tests | 0 (update assertions) |
| 1.2 (EngineProfile) | 3 | 0 (delete tests) |
| 1.3 (ParsingError raise) | ~15 parser tests | ~8 (replace None asserts) |
| 1.4 (parse_list raise) | ~8 parser tests | ~8 (bad JSON raising tests) |
| 1.5 (ParsingError move) | ~5 | 0 (import path change) |
| 1.6 (delete engines.py) | 4+2 | 0 (delete + rewrite) |
| 2.1 (execute_pty port) | 3 | 3 (abstract method test) |
| 2.2 (CliTransport.execute_pty) | 0 | ~5 (PTY tests) |
| 2.3 (container uses transport) | 1 | 0 (import change) |
| 2.4 (remove binary) | ~5 | 0 (update constructors) |
| 3.1-3.4 (factory DI) | ~5 | 2 (injection tests) |
| 4.1 (_check_result) | 0 | 4 (create error tests) |
| 4.2 (--format json) | 0 | 0 (runtime behavior change) |
| 4.3 (port parse fix) | 0 | 2 (malformed port tests) |
| 4.4 (sha256 format) | 2 | 2 (format consistency tests) |
| 4.5 (thread name) | 0 | 0 (cosmetic) |
| 5.1-5.3 (dedup) | 0 | ~4 (BaseCliParser tests) |

**Total estimated test changes**: ~45 existing tests modified, ~40 new tests added.

---

## Risk Assessment

| Change | Risk | Mitigation |
|--------|------|-----------|
| StrEnum conversion | Medium — string comparison behavior changes | Run existing enum tests after change; verify `str()` output |
| ParsingError from None | High — all callers and tests expect `None` | Grep for all `is None` / `== None` patterns on parser outputs first |
| Factory DI | Medium — changes `RuntimeFactory()` default behavior | `_default_providers()` preserves zero-arg convenience |
| PTY in Transport | Medium — changes PTY test location | Move existing PTY tests to transport test file |
| `--format json` on inspect | Low — but runtime behavior differs | Verify with real Docker/Podman; inspect already returns JSON by default |
| Delete engines.py | Low — few consumers | Grep for all `engines.` references first |