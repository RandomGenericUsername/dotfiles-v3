# OCI-Runtime Module — Comprehensive Audit Report

**Module:** `src/shared/oci-runtime/`  
**Purpose:** Runtime-agnostic OCI container management (Docker/Podman) via hexagonal architecture  
**Language:** Python 3.12+  
**Lines of Source:** ~1,400 across 20 files  
**Lines of Tests:** ~3,500 across 35 files  
**Audit Date:** 2026-05-29  

---

## Executive Summary

The module follows hexagonal architecture correctly (Domain → Ports → Adapters → Factory DI root). The skeleton is clean. Of the **27 findings** identified, **21 have been resolved** and **5 remain open**. Resolved: 2 critical bugs (bytes vs str type violations in volume/network managers), 6 high-severity issues (DRY violation, silent fallbacks, wasteful stack creation, unnecessary `object.__setattr__` frozen consistency, execute_pty dead code, factory import-time side effects), 7 medium-severity issues (ContainerState `StrEnum` + `ContainerInfo.state` re-type, domain types public API expansion, OCP violation via `RuntimeProvider` port, port behavioral contract tests + integration refactor, `_check_result` hasattr guard removed, `exec()` returns `ExecOutput` preserving stderr), and 5 low-severity issues (Podman `--quiet` build flag simplifying `parse_build_output` for both runtimes, streaming transport deadlock/CPU spin fixed, streaming FD leak reaping fixed, overly broad `except Exception` narrowed, expanded `create()` test assertions with CLI command verification).

**Previous audit report (`docs/oci-runtime-audit-report.md`) contained factual errors** — this document replaces it entirely.

---

## Finding Index

| # | Severity | Finding | File(s) |
|---|----------|---------|---------|
| 1 | 🔴 Critical | Volume/Network `create()` returns `bytes` instead of `str` | ✅ RESOLVED |
| 2 | 🔴 Critical | Volume/Network `inspect()`/`list()` pass `bytes` to `str`-typed parsers | ✅ RESOLVED |
| 3 | 🟠 High | Duplicate `BaseCliParser` and `parse_size_to_bytes` (DRY violation) | ✅ RESOLVED |
| 4 | 🟠 High | `build_parsers` and `build_capabilities` have silent fallbacks | ✅ RESOLVED |
| 5 | 🟠 High | `RuntimeFactory.available()` creates full engine stacks wastefully | ✅ RESOLVED |
| 6 | 🟠 High | `_resolve_config` uses `object.__setattr__` unnecessarily | ✅ RESOLVED |
| 7 | 🟠 High | `execute_pty` is dead code with critical implementation bugs | ✅ RESOLVED |
| 8 | 🟡 Medium | `ContainerState` enum is dead code (3 states vs 7 engine states) | ✅ RESOLVED |
| 9 | 🟡 Medium | Domain types missing from public API (`__all__`) | ✅ RESOLVED |
| 10 | 🟡 Medium | Factory has hardcoded runtime branches (OCP violation) | ✅ RESOLVED |
| 11 | 🟡 Medium | Tests bypass port abstractions, couple to concrete `Cli*` classes | ✅ RESOLVED |
| 12 | 🟡 Medium | `ContainerInfo.state` typed as `str` instead of `ContainerState` | ✅ RESOLVED |
| 13 | 🔵 Low | Podman `parse_build_output` too simplistic (last-line heuristic) | ✅ RESOLVED |
| 14 | 🔵 Low | Streaming path in `CliTransport` has file descriptor leak risk | ✅ RESOLVED |
| 15 | 🔵 Low | Overly broad `except Exception` in `CliRuntime` | ✅ RESOLVED |
| 16 | 🔵 Low | `selector.select(timeout=0.1)` suboptimal + stdin deadlock risk | ✅ RESOLVED |
| 17 | 🔵 Low | Unit tests don't assert `create()` return values | ✅ RESOLVED |
| **18** | 🔴 **Critical** | **`CliRuntime.ping()` calls nonexistent `docker ping` command** | ✅ RESOLVED |
| **19** | 🔴 **Critical** | **`ContainerManager.logs(follow=True)` blocks indefinitely without streaming** | ✅ RESOLVED |
| **20** | 🟠 **High** | **Factory has import-time side effects via module-level `register_provider()`** | ✅ RESOLVED |
| **21** | 🟡 **Medium** | **`CliBaseManager._check_result` uses `hasattr` circumventing type safety** | ✅ RESOLVED |
| **22** | 🟡 **Medium** | **`ContainerManager.exec()` returns bare `tuple[int, str]`, silently drops stderr** | ✅ RESOLVED |
| **23** | 🔵 **Low** | **`ContainerEngine.info()` returns opaque `dict[str, Any]` instead of typed object** | ✅ RESOLVED |
| **24** | 🔵 **Low** | **Domain type inconsistencies: `RuntimeKind` not `StrEnum`, `BuildContext.build_file` dual semantics, `PortMapping.host_ip` default** | `domain/enums.py`, `domain/types.py` |
| **25** | 🔵 **Low** | **Mutable module-level engine presets + `RuntimePreference.get_binary()` contradicts documented contract** | `engines.py`, `ports/capabilities.py` |
| **26** | 🔵 **Low** | **`ImageManager.build()` temporary file leaks on process crash** | `adapters/managers/image.py` |

---

## 🔴 CRITICAL BUGS

### Finding #1: Volume/Network `create()` Returns `bytes` Instead of `str`

**File:** `adapters/managers/volume.py:20`, `adapters/managers/network.py:20`

**Code:**
```python
def create(self, name: str, ...) -> str:        # type hint says str
    ...
    result = self._transport.execute(cmd)
    return result.stdout.strip()                # stdout is bytes, .strip() returns bytes
```

**Problem:** `ExecResult.stdout` is typed as `bytes`. Calling `bytes.strip()` returns `bytes`, not `str`. The `-> str` type hint is a lie. Any caller using string formatting or concatenation gets `b"my-vol"` instead of `"my-vol"`.

**Root cause:** The container and image managers decode bytes to string with `.decode("utf-8", errors="replace")`, but the volume and network managers do not.

**Detection gap:** Tests only call `assert_called_once()` — they never assert on the return value.

### Deep Investigation — Full Code Path Trace

#### 1. The Contract

`ports/transport.py:7-10` defines `ExecResult`:
```python
@dataclass
class ExecResult:
    returncode: int
    stdout: bytes
    stderr: bytes
```

`ports/managers.py:92` and `ports/managers.py:112` define the abstract contracts:
```python
class VolumeManager(ABC):
    def create(self, name: str, ...) -> str: ...   # returns str

class NetworkManager(ABC):
    def create(self, name: str, ...) -> str: ...   # returns str
```

The `Transport` ABC (`ports/transport.py:13-24`) declares `execute()` returning `ExecResult` with `stdout: bytes`. This is **correct** — the transport is encoding-agnostic raw I/O. The manager is responsible for decoding.

#### 2. All `result.stdout` Usages in the Source Tree

Every place `result.stdout` is consumed across all 4 managers + engine:

| File | Line | Current Code | Returns/Passes |
|------|------|-------------|----------------|
| `volume.py` | 20 | `result.stdout.strip()` | `bytes` 🔴 |
| `volume.py` | 40 | `self._parser.parse_inspect(result.stdout)` | `bytes` 🔴 |
| `volume.py` | 51 | `self._parser.parse_list(result.stdout)` | `bytes` 🔴 |
| `volume.py` | 56 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `network.py` | 20 | `result.stdout.strip()` | `bytes` 🔴 |
| `network.py` | 50 | `self._parser.parse_inspect(result.stdout)` | `bytes` 🔴 |
| `network.py` | 61 | `self._parser.parse_list(result.stdout)` | `bytes` 🔴 |
| `network.py` | 66 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `container.py` | 95 | `result.stdout.decode("utf-8", errors="replace").strip()` | `str` ✅ |
| `container.py` | 132 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `container.py` | 145 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `container.py` | 155 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `container.py` | 167 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `container.py` | 172 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `image.py` | 50 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `image.py` | 72 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `image.py` | 92 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `image.py` | 103 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `image.py` | 110 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `engine/cli.py` | 65 | `result.stdout.decode("utf-8", errors="replace").strip()` | `str` ✅ |
| `engine/cli.py` | 80 | `result.stdout.decode("utf-8", errors="replace").strip()` | `str` ✅ |

Key observation: **Volume and network managers decode correctly in `prune()` but NOT in `create()`/`inspect()`/`list()`** — inconsistency within the same two files strongly suggests oversight, not design.

#### 3. Git History Investigation

Three commits touch these files:

| Commit | Message | What Changed |
|--------|---------|-------------|
| `09a8c9c` | *"feat: stabilize oci-runtime with bytes-safe transport and context-aware errors"* | Original implementation. Container/image already had `.decode()`. Volume/network used raw `bytes.strip()`. |
| `423ee5a` | *"refactor(oci-runtime): instance factory with explicit RuntimePreference + DI"* | Factory restructure. Manager code unchanged. |
| `5118502` | *"fixes based on oci-runtime-audit-report.md"* | **Latest commit.** Fixed `prune()` — replaced fake hardcoded dicts (`{"deleted": 1, "space_reclaimed": 0}`) with real parser calls using `.decode()`. But **missed** `create()`/`inspect()`/`list()`. |

The diff of commit `5118502` for `volume.py`:
```diff
-        self._transport.execute(cmd)
-        return {"deleted": 1, "space_reclaimed": 0}
+        result = self._transport.execute(cmd)
+        return self._parser.parse_prune(result.stdout.decode("utf-8", errors="replace"))
```

The same pattern was applied to `network.py`. The author fixed `prune()` with proper decoding but did not fix the other three methods in the same files.

Additionally, the original `BaseManager` (with `_check_result`) lived in **`ports/managers.py`** (ports layer — architecture violation). Commit `5118502` extracted it into **`adapters/managers/base.py`** as `CliBaseManager` (correct adapters layer), proving ongoing architectural cleanup.

#### 4. Crash Scenarios for Downstream Callers

When a caller receives `bytes` instead of `str` from `volume.create()` or `network.create()`:

| Operation | Code | Result |
|-----------|------|--------|
| f-string | `f"Volume {name} created"` | `"Volume b'myvol' created"` — `b''` prefix leaks |
| `.startswith()` | `name.startswith("test-")` | `TypeError: startswith first arg must be bytes or a tuple of bytes, not str` |
| Concatenation | `"prefix-" + name` | `TypeError: can only concatenate str (not "bytes") to str` |
| `.replace()` | `name.replace("vol", "volume")` | `TypeError: a bytes-like object is required, not 'str'` |

#### 5. Callers Across the Codebase

| File | Line | Usage | Impact |
|------|------|-------|--------|
| `test_real_runtime.py` | 73 | `name = engine.volumes.create(vol_name)` then `name.strip()` | Works on bytes too — masks bug |
| `test_real_runtime.py` | 82 | `name = engine.networks.create(net_name)` then `name.strip()` | Works on bytes too — masks bug |
| `test_workflows.py` | 214 | `assert name == b"myvol"` | **Expects bytes! Will break when fixed** |
| `test_workflows.py` | 233 | `docker_engine.volumes.create(...)` — return discarded | No impact |
| `test_workflows.py` | 260 | `assert name == b"mynet"` | **Expects bytes! Will break when fixed** |
| `test_workflows.py` | 276 | `docker_engine.networks.create(...)` — return discarded | No impact |

#### 6. Parsers — Why `bytes` Works Accidentally (Finding #2 Connection)

All `parse_inspect()` and `parse_list()` methods call `json.loads(raw)` internally. Python 3.6+ `json.loads()` accepts `bytes` natively, so passing `bytes` instead of `str` works at runtime — but violates the type contract (`raw: str`).

Methods that do **not** tolerate bytes:
- `parse_size_to_bytes()` uses `size_str.upper()` → `AttributeError: 'bytes' object has no attribute 'upper'`
- `BaseCliParser.parse_prune()` uses `re.compile(...).findall(raw)` — regex on bytes returns `bytes` matches instead of `str` matches
- `is_not_found_error()` uses `in stderr` — but stderr is always decoded by `_check_result` in `base.py:42`

Fortunately, `parse_prune()` is only called from `prune()` methods (which already decode correctly in all 4 managers). The volume/network `inspect()` and `list()` methods happen to work because `json.loads()` accepts bytes — this is a latent bug.

---

### Prototype Validation

**File:** `dev/validation/oci_runtime/finding-1-decode-stdout-approach.py`

A standalone Python script was created to validate the approach end-to-end.

#### Prototype Architecture

The script simulates the full layer stack:
1. `ExecResult` dataclass (same as `ports/transport.py`)
2. `CliBaseManager` with `_decode_stdout()` method (proposed fix location)
3. `BuggyVolumeManager`/`BuggyNetworkManager` — current broken implementation
4. `FixedVolumeManager`/`FixedNetworkManager` — proposed fixed implementation
5. `FixedContainerManager`/`FixedImageManager` — refactored to use helper
6. Simplified parsers (`VolumeParser`, `NetworkParser`) — same `json.loads()` logic
7. Domain types (`VolumeInfo`, `NetworkInfo`) — simplified dataclasses
8. Non-UTF-8 edge case simulation (`b"valid_name\xff\xfe"`)

#### Prototype Results (Full Output)

```
========================================================================
PROTOTYPE: _decode_stdout approach for Finding #1
========================================================================

─── 1. CURRENT BUG: volume/network create() returns bytes ───

  volume.create() returns type: bytes
  volume.create() returns value: b'myvol'
  f-string: f'Volume b'myvol' created' -> "Volume b'myvol' created"

  network.create() returns type: bytes
  network.create() returns value: b'mynet'
  f-string: f'Network b'mynet' created' -> "Network b'mynet' created"

  CRASH SCENARIOS with current buggy code:
    f-string:       f'Volume {name} created'
      -> 'Volume b'mynet' created'  (b'' prefix leaks)
    .startswith():  name.startswith('my')
      -> TypeError: startswith first arg must be bytes or a tuple of bytes, not str
    concatenation:  'prefix-' + name
      -> TypeError: can only concatenate str (not "bytes") to str

─── 2. FIXED: _decode_stdout makes everything str ───

  volume.create() returns type: str
  volume.create() returns value: 'myvol'
  f-string: f'Volume myvol created' -> 'Volume myvol created'
  .startswith('my'):            True
  'prefix-' + name:             'prefix-myvol'

  network.create() returns type: str
  network.create() returns value: 'mynet'
  f-string: f'Network mynet created' -> 'Network mynet created'

─── 3. Parser compatibility (json.loads with str vs bytes) ───

  Buggy: parse_inspect(result.stdout) [bytes]  -> name=myvol (works but type hint lies)
  Fixed: parse_inspect(_decode_stdout(...)) [str] -> name=myvol
  json.loads(bytes) works: [{'Name': 'vol1', 'Driver': 'local'}]
  json.loads(str)    works: [{'Name': 'vol1', 'Driver': 'local'}]
  raw_str.startswith('['):         True
  raw_bytes.startswith('['):        TypeError: startswith first arg must be bytes or a tuple of bytes, not str

─── 4. Edge case: non-UTF-8 output ───

  Input bytes: b'valid_volume_name\xff\xfe'
  Decoded str: 'valid_volume_name��'
  (errors='replace' substitutes bad bytes with U+FFFD)
  .strip() works: 'valid_volume_name��'
  No crash: ✅

─── 5. All 4 managers use same _decode_stdout ───

  ContainerManager.run():    type=str, val='abc123'
  ContainerManager.inspect(): type=str
  ImageManager.build():       type=str, val='sha256:abc123\n'
  VolumeManager.create():     type=str, val='myvol'
  NetworkManager.create():    type=str, val='mynet'
```

#### What the Prototype Validates

| Check | Result | Evidence |
|-------|--------|----------|
| Bug is real | ✅ Confirmed | `type(bytes)` returned, `.startswith()` crashes, f-string leaks `b''` |
| Fix returns str | ✅ Confirmed | `type(str)` returned, all string ops work |
| Non-UTF-8 safe | ✅ Confirmed | `errors='replace'` substitutes bad bytes, no crash |
| Parser compatibility | ✅ Confirmed | `json.loads()` works with both bytes and str |
| All 4 managers consistent | ✅ Confirmed | Same helper call pattern in every method |
| `.strip()` after decode | ✅ Confirmed | `self._decode_stdout(result.stdout).strip()` works correctly |

---

### Proposed Solution

#### Approach: `_decode_stdout()` helper in `CliBaseManager`

Instead of adding raw `.decode()` calls to every method (the current pattern in container/image), extract a reusable helper method in the shared base class. This is consistent with `_resolve_val()` and `_check_result()` which already live in `CliBaseManager`.

**Add to** `adapters/managers/base.py`:
```python
def _decode_stdout(self, data: bytes) -> str:
    return data.decode("utf-8", errors="replace")
```

#### Then fix each affected method:

**`volume.py`** (3 sites):
- Line 20: `result.stdout.strip()` → `self._decode_stdout(result.stdout).strip()`
- Line 40: `self._parser.parse_inspect(result.stdout)` → `self._parser.parse_inspect(self._decode_stdout(result.stdout))`
- Line 51: `self._parser.parse_list(result.stdout)` → `self._parser.parse_list(self._decode_stdout(result.stdout))`

**`network.py`** (3 sites):
- Line 20: `result.stdout.strip()` → `self._decode_stdout(result.stdout).strip()`
- Line 50: `self._parser.parse_inspect(result.stdout)` → `self._parser.parse_inspect(self._decode_stdout(result.stdout))`
- Line 61: `self._parser.parse_list(result.stdout)` → `self._parser.parse_list(self._decode_stdout(result.stdout))`

**`container.py`** (6 sites, refactor to use helper):
- Line 95: `result.stdout.decode("utf-8", errors="replace").strip()` → `self._decode_stdout(result.stdout).strip()`
- Line 132: `result.stdout.decode("utf-8", errors="replace")` → `self._decode_stdout(result.stdout)`
- Line 145: same
- Line 155: same
- Line 167: same
- Line 172: same

**`image.py`** (5 sites, refactor to use helper):
- Line 50: `result.stdout.decode("utf-8", errors="replace")` → `self._decode_stdout(result.stdout)`
- Line 72: same
- Line 92: same
- Line 103: same
- Line 110: same

#### Tests to update

**`test_workflows.py:214`**: `assert name == b"myvol"` → `assert name == "myvol"`
**`test_workflows.py:260`**: `assert name == b"mynet"` → `assert name == "mynet"`

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Domain: pure Python, no I/O | ✅ Unchanged | Domain types not modified |
| Ports: ABCs only, no implementation | ✅ Unchanged | `ExecResult.stdout: bytes` preserved in port |
| Adapters: implement contracts, contain I/O | ✅ | `_decode_stdout` in `CliBaseManager` (adapter layer) |
| Factory: only place wiring ports to adapters | ✅ Unchanged | No factory changes needed |

The fix respects the clean architecture:
- Transport (port) remains encoding-agnostic → `stdout: bytes`
- `CliBaseManager` (adapter) provides the decode helper → correct I/O boundary layer
- Each manager (adapter) uses the helper → orchestration responsibility
- Parsers (adapter) receive `str` → type contract satisfied

#### Alternative Considered: Change `ExecResult.stdout` to `str`

Changing `ExecResult.stdout` from `bytes` to `str` and decoding in `CliTransport.execute()` was considered but rejected:

| Pro | Con |
|-----|-----|
| Single decode point (DRY) | Transport would assume encoding (violates I/O boundary purity) |
| Simpler manager code | Streaming `on_output` callback takes `bytes` — path mismatch |
| No per-method changes | Would require `CliTransport` to decode all output upfront |

The `on_output: Callable[[bytes], None]` callback in the transport's streaming path receives raw bytes for real-time output processing. If `ExecResult.stdout` were `str`, the streaming accumulator would need to decode bytes and re-encode them for the callback — or change the callback signature, breaking the port contract.

**Verdict**: The `_decode_stdout` helper approach is architecturally superior to changing the transport return type.

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-05-29
**Changes applied:**

1. **`adapters/managers/base.py`** — Added `_decode_stdout(data: bytes) -> str` to `CliBaseManager`
2. **`adapters/managers/volume.py`** — Fixed 3 sites: `create()`, `inspect()`, `list()` now decode before returning/passing to parsers
3. **`adapters/managers/network.py`** — Fixed 3 sites: `create()`, `inspect()`, `list()` now decode before returning/passing to parsers
4. **`adapters/managers/container.py`** — Refactored 6 sites to use `_decode_stdout` helper
5. **`adapters/managers/image.py`** — Refactored 5 sites to use `_decode_stdout` helper
6. **`tests/unit/adapters/test_cli_volume_manager.py`** — Added `test_create_returns_str`, `test_list_returns_list_of_volume_info`, `test_inspect_returns_volume_info`, `test_decode_stdout_converts_bytes_to_str`, `test_decode_stdout_handles_non_utf8`, `test_decode_stdout_strip_preserved`
7. **`tests/unit/adapters/test_cli_network_manager.py`** — Added `test_create_returns_str`, `test_list_returns_list_of_network_info`, `test_inspect_returns_network_info`
8. **`tests/integration/functional/test_workflows.py`** — Updated 2 byte-string assertions to str
9. **`tests/integration/integration/test_manager_commands.py`** — Updated 2 byte-string assertions to str

**Solution rationale:** Extracted `_decode_stdout()` helper in `CliBaseManager` (adapters layer) rather than changing the transport return type (ports layer). This preserves hexagonal architecture: transport remains encoding-agnostic (`stdout: bytes`), managers decode before returning to callers or passing to parsers. See the full investigation above for why this approach was chosen over alternatives.

**Verification:** 484 tests pass (0 failures) across unit and integration suites.

---

---

### Finding #18: `CliRuntime.ping()` Calls Nonexistent `docker ping` Command

**File:** `adapters/engine/cli.py:101-107`

**Code:**
```python
def ping(self) -> bool:
    try:
        result = self._transport.execute([self._binary, "ping"])
        return result.returncode == 0
    except (RuntimeNotAvailableError, subprocess.TimeoutExpired, OSError):
        return False
```

**Problem:** Docker has no `docker ping` subcommand. This will **always return `False`** for Docker. The only runtime that supports `podman ping` is Podman (and only in recent versions), making this method virtually dead code for the majority of users.

**Root cause:** The `ping()` method was modeled after generic network health-check patterns without verifying that the underlying runtime actually supports it. `docker info` is the equivalent health-check command for Docker.

**Detection gap:** The integration test `test_engine_lifecycle.py:137-144` explicitly asserts `docker ping` is the correct command, enshrining the bug in the test suite:
```python
def test_ping_calls_ping_command(self, caps, mock_managers):
    transport = RecordingTransport("docker", {
        "docker ping": ExecResult(returncode=0, stdout=b"", stderr=b""),
    })
    ...
    assert transport.calls[0].command == ["docker", "ping"]
```

**Affected runtime matrix:**
| Runtime | `{binary} ping` exists? | `{binary} info` exists? |
|---------|------------------------|------------------------|
| Docker | ❌ No | ✅ Yes |
| Podman | ✅ Since v4.x | ✅ Yes |

### Deep Investigation — Full Code Path Trace

#### 1. The Port Contract

`ports/engine.py:43-44` defines `ping()` as an abstract method:
```python
class ContainerEngine(ABC):
    ...
    @abstractmethod
    def ping(self) -> bool: ...
```

`adapters/engine/cli.py:101-107` implements it:
```python
def ping(self) -> bool:
    try:
        result = self._transport.execute([self._binary, "ping"])
        return result.returncode == 0
    except (RuntimeNotAvailableError, subprocess.TimeoutExpired, OSError):
        return False
```

#### 2. Production Caller Analysis

A full source tree search for `.ping(` across `src/oci_runtime/` found **zero callers**. The method is only referenced in its own definition and in test files.

#### 3. Runtime Command Matrix

| Runtime | `{binary} ping` | `{binary} info` |
|---------|----------------|-----------------|
| Docker | ❌ Not a valid command | ✅ `docker info` exits 0 |
| Podman v4+ | ✅ `podman ping` exits 0 | ✅ `podman info` exits 0 |

Live validation confirmed: `docker ping` exits with code 1 and outputs `"docker: unknown command: docker ping"`. `docker info` exits with code 0 and produces 1505B of output.

#### 4. Existing Alternatives

`is_available()` and `info()` both cover the health-check concern:

| Method | What It Checks | Use Case |
|--------|---------------|----------|
| `is_available()` | Binary exists + `--version` returns 0 | Binary installation check |
| `info()` | Daemon responds to `{binary} info` | Daemon health check |
| `ping()` 🔴 | `{binary} ping` returns 0 | Broken — no universal command |

There is no scenario where `info()` returns successfully but `ping()` would return `True` — the reverse is true: `ping()` always returns `False` for Docker while `info()` works correctly.

### Prototype Validation

**File:** `dev/validation/oci_runtime/finding-18-remove-ping.py`

A standalone Python script validates the removal approach end-to-end with 17 tests.

#### Prototype Architecture

1. Simplified `ContainerEngine` ABC (without `ping()`) — port layer
2. `CliRuntime` implementing the ABC (without `ping()`) — adapter layer
3. `RecordingTransport` with configurable mock responses
4. `MockEngine` test double (without `ping()`)
5. Live `docker ping` / `docker info` command verification

#### Prototype Results

```
PROTOTYPE: Finding #18 — Remove ping() from ContainerEngine

  TEST 1: 'docker ping' does not exist (live check)
    ✅ PASS | 'docker ping' returns non-zero  (exit code=1)
    ✅ PASS | stderr contains "unknown command"

  TEST 2: 'docker info' works as health check (live check)
    ✅ PASS | 'docker info' returns 0 (healthy)
    ✅ PASS | produces 1505B output

  TEST 3: No production code calls ping()
    ✅ PASS | Zero callers found in src/oci_runtime/

  TEST 4: ContainerEngine ABC works without ping()
    ✅ PASS | ValidEngine instantiates
    ✅ PASS | is_available() works
    ✅ PASS | version() works
    ✅ PASS | info() works

  TEST 5: CliRuntime works without ping()
    ✅ PASS | CliRuntime is ContainerEngine
    ✅ PASS | is_available() returns True
    ✅ PASS | info() returns parsed dict
    ✅ PASS | No AttributeError for missing ping

  TEST 6: MockEngine works without ping()
    ✅ PASS | MockEngine instantiates
    ✅ PASS | is_available() works
    ✅ PASS | info() works

RESULTS: 17 PASSED, 0 FAILED
```

#### What the Prototype Validates

| Check | Result | Evidence |
|-------|--------|----------|
| `docker ping` is broken | ✅ Confirmed | Exit code 1, "unknown command" |
| `docker info` works as health check | ✅ Confirmed | Exit code 0, meaningful output |
| Zero production callers of `ping()` | ✅ Confirmed | Dead code |
| Engine ABC works without `ping()` | ✅ Confirmed | Subclass instantiates, all methods work |
| CliRuntime works without `ping()` | ✅ Confirmed | `is_available()`, `info()` both function |
| MockEngine works without `ping()` | ✅ Confirmed | Test doubles still valid |

### Proposed Solution

#### Approach: Remove `ping()` entirely — broken abstraction at the port level

`ping()` is never called by any production code. The command `docker ping` doesn't exist — it returns `False` for every Docker caller. `is_available()` (binary exists + `--version` responds) and `info()` (daemon responds with system info) already cover the health-check use case correctly. The method is dead code and the abstraction is invalid.

**Remove** `ports/engine.py:43-44` — Delete `ping()` from the `ContainerEngine` ABC.

**Remove** `adapters/engine/cli.py:101-107` — Delete `ping()` implementation from `CliRuntime`.

#### Tests to Remove

| File | What to Remove |
|------|----------------|
| `tests/unit/ports/test_engine.py:47-48` | `test_ping_is_abstract` |
| `tests/unit/adapters/test_cli_runtime.py:148-159` | `test_ping_still_catches_os_error` |
| `tests/integration/integration/test_engine_lifecycle.py:116-144` | Entire `TestEnginePing` class (4 tests) |
| `tests/integration/contract/test_interface_compliance.py:118` | `"ping"` from `expected_methods` set |
| `tests/integration/contract/test_interface_compliance.py:147` | `assert callable(runtime.ping)` |
| `tests/integration/smoke/test_real_runtime.py:33-35` | `test_live_engine_ping_works` |
| `tests/integration/integration/test_factory_wiring.py:118` | `def ping(self): return True` from `MockEngine` |

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Domain: pure Python, no I/O | ✅ Unchanged | No domain types touched |
| Ports: ABCs only, no implementation | ✅ | Removing a broken abstraction — `ping()` was an operation without a universal runtime mapping |
| Adapters: implement contracts, contain I/O | ✅ | Removing adapter code that issued a nonexistent command |
| Factory: only DI composition root | ✅ Unchanged | No factory changes needed |

The port abstraction `ping()` was invalid because there is no runtime-agnostic command that implements "ping" for both Docker and Podman. `is_available()` and `info()` cover the same use case correctly:
- `is_available()` → binary exists + `--version` responds
- `info()` → daemon is responsive

Removing `ping()` from the port layer is architecturally correct — it acknowledges that the abstraction was not universally realizable.

**Status:** ✅ RESOLVED
**Date:** 2026-06-02
**Changes applied:**

1. **`ports/engine.py`** — Removed `ping()` abstract method from `ContainerEngine` ABC (line 43-44)
2. **`adapters/engine/cli.py`** — Removed `ping()` implementation from `CliRuntime` (lines 101-107)
3. **`tests/unit/ports/test_engine.py`** — Removed `test_ping_is_abstract`
4. **`tests/unit/adapters/test_cli_runtime.py`** — Removed `test_ping_still_catches_os_error`
5. **`tests/integration/integration/test_engine_lifecycle.py`** — Removed entire `TestEnginePing` class (4 tests)
6. **`tests/integration/contract/test_interface_compliance.py`** — Removed `"ping"` from `expected_methods` set and `assert callable(runtime.ping)`
7. **`tests/integration/smoke/test_real_runtime.py`** — Removed `test_live_engine_ping_works`
8. **`tests/integration/integration/test_factory_wiring.py`** — Removed `def ping(self): return True` from `MockEngine`

**Solution rationale:** `ping()` is never called by any production code. The command `docker ping` doesn't exist — it returns `False` for every Docker caller. `is_available()` (binary exists + `--version` responds) and `info()` (daemon responds with system info) already cover the health-check use case correctly. Removing `ping()` from the port layer is architecturally correct — it acknowledges that the abstraction was not universally realizable.

**Verification:** 638 tests pass (0 failures) across unit and integration suites.

---

### Finding #19: `ContainerManager.logs(follow=True)` Blocks Indefinitely Without Streaming

**File:** `adapters/managers/container.py:159-167`

**Code:**
```python
def logs(self, container: str, follow: bool = False, tail: int | None = None) -> str:
    cmd = [self._transport.get_runtime_binary(), "logs", container]
    if follow:
        cmd.append("--follow")
    if tail is not None:
        cmd.extend(["--tail", str(tail)])
    result = self._transport.execute(cmd)
    self._check_result(result, cmd, operation="get logs", entity=container, not_found=ContainerNotFoundError)
    return self._decode_stdout(result.stdout)
```

**Problem:** When `follow=True`, Docker/Podman `logs --follow` blocks until the container stops or the connection is closed:
1. `self._transport.execute(cmd)` is called with **no `stream=True`** and **no `timeout`** — the call blocks forever.
2. The return type is `str` — incompatible with streaming. Even if the call returned, there is no mechanism to deliver incremental output.
3. The `stream` parameter on `Transport.execute()` exists precisely for this use case but is never wired.

**Root cause:** The `logs()` method was designed for the non-following case (fetch-and-return) but the `follow` parameter was added without implementing the streaming code path.

**Affected usage:**
```python
engine.containers.logs("my-container", follow=True)  # hangs indefinitely
```

### Proposed Solution

#### Approach: Change `logs()` return type to `Iterator[str]` — single method, honest return type

The return type `str` cannot represent an ongoing stream. The `follow` parameter is correct domain modeling (one operation: "get logs"), but the return type must be `Iterator[str]` to handle both the fetch (finite) and stream (infinite) cases.

**Non-follow:** yields the entire decoded stdout as a single chunk. The iterator exhausts immediately.

**Follow:** uses a `threading.Thread` + `queue.Queue` bridge to convert the transport's `on_output` callback pattern into an `Iterator[str]`. The background thread calls `self._transport.execute(cmd, stream=True, on_output=callback)`, the callback decodes each chunk and puts it in the queue, and the main thread yields from the queue. Errors from the background thread are stored and re-raised when the iterator exhausts.

This reuses three established patterns:
- `Transport.execute(stream=True, on_output=...)` — already exists at `ports/transport.py:20-22`
- `threading.Thread` — already used in `CliTransport` for stdin deadlock fix (Fix 16b)
- `self._decode_stdout()` from `CliBaseManager` — already used throughout

**Change** `ports/managers.py:67` — Return type `str` → `Iterator[str]`:
```python
from collections.abc import Iterator

class ContainerManager(ABC):
    @abstractmethod
    def logs(self, container: str, follow: bool = False, tail: int | None = None) -> Iterator[str]: ...
```

**Update** `adapters/managers/container.py:159-167`:
```python
from collections.abc import Iterator
from queue import Queue
from threading import Thread

def logs(self, container: str, follow: bool = False, tail: int | None = None) -> Iterator[str]:
    cmd = [self._transport.get_runtime_binary(), "logs", container]
    if follow:
        cmd.append("--follow")
    if tail is not None:
        cmd.extend(["--tail", str(tail)])

    if not follow:
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="get logs", entity=container, not_found=ContainerNotFoundError)
        yield self._decode_stdout(result.stdout)
        return

    queue: Queue[str | None] = Queue()
    errors: list[BaseException] = []

    def _on_output(data: bytes) -> None:
        queue.put(data.decode("utf-8", errors="replace"))

    def _run() -> None:
        try:
            self._transport.execute(cmd, stream=True, on_output=_on_output)
        except BaseException as e:
            errors.append(e)
        finally:
            queue.put(None)

    Thread(target=_run, daemon=True).start()

    while True:
        chunk = queue.get()
        if chunk is None:
            break
        yield chunk

    if errors:
        raise errors[0]
```

#### Backward Compatibility

`logs()` return changes from `str` to `Iterator[str]`. All callers must update:

| Before | After |
|--------|-------|
| `logs = mgr.logs("c1")` | `logs = "".join(mgr.logs("c1"))` |
| `assert mgr.logs("c1") == "out"` | `assert "".join(mgr.logs("c1")) == "out"` |
| `assert isinstance(mgr.logs("c1"), str)` | `assert isinstance(mgr.logs("c1"), Iterator)` |

For the follow case, callers iterate directly:
```python
for chunk in mgr.logs("c1", follow=True):
    sys.stdout.write(chunk)
```

#### Error Handling

- **Non-follow:** `_check_result` raises immediately if `returncode != 0`, before any yield — same as today.
- **Follow:** Errors from the background thread are stored and re-raised when the iterator exhausts. Chunks that arrived before the error are yielded to the caller first. This means `ContainerNotFoundError` is reported when the stream ends — acceptable since `docker logs --follow` on a running container only fails at start (container unknown) or end (container dies), both of which the caller observes.
- **Lazy iteration:** The iterator does not execute the transport call until the first `next()`. Creating the iterator is cheap.

#### Tests to Update

| File | Change |
|------|--------|
| `tests/unit/ports/test_container_manager_contract.py:85-89` | `test_logs_returns_str` → `test_logs_returns_iterator`, `isinstance(result, str)` → `isinstance(result, Iterator)` |
| `tests/integration/integration/test_manager_commands.py:252-257` | `result = mgr.logs("ctr1")` → `result = "".join(mgr.logs("ctr1"))` |
| `tests/integration/integration/test_manager_commands.py:259-263` | `mgr.logs("ctr1", follow=True, tail=50)` → `list(mgr.logs("ctr1", follow=True, tail=50))` to exhaust |
| `tests/integration/functional/test_workflows.py:119-120` | `logs = mgr.logs("ctr1")` then `assert logs == "..."` → `assert "".join(mgr.logs("ctr1")) == "..."` |
| `tests/integration/functional/test_workflows.py:155-156` | Same pattern — `logs =` → `"".join(...)` |
| `tests/integration/boundary/test_empty_outputs.py:87` | `assert mgr.logs("ctr1") == ""` → `assert "".join(mgr.logs("ctr1")) == ""` |
| `tests/integration/smoke/test_real_runtime.py:51-52` | `logs = ...logs(cid)` then `assert isinstance(logs, str)` → `assert isinstance("".join(mgr.logs(cid)), str)` |
| No change needed | `tests/integration/contract/test_interface_compliance.py` — only checks `callable(mgr.logs)`, method name unchanged |

#### Prototype Validation

**File:** `dev/validation/oci_runtime/finding-19-logs-iterator.py`

A standalone Python script validates the approach end-to-end with 25 tests covering:
- Port contract: `logs()` is abstract, return type is annotated as `Iterator[str]`
- Non-follow mode: yields full output as single chunk, lazy iteration, `"".join()` works
- Follow mode: streams multiple chunks in order via thread + Queue, works with tail option
- Empty output: both modes produce empty strings
- Error handling: non-follow raises immediately, follow mode delivers chunks before error and re-raises on exhaustion
- Iterator semantics: exhausts correctly, multiple `list()` calls on same iterator produce correct results

```
RESULTS: 25 PASSED, 0 FAILED
```

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|---|---|---|
| Domain: pure Python, no I/O | ✅ Unchanged | No domain types touched |
| Ports: ABCs only, no implementation | ✅ | `logs()` stays on `ContainerManager` ABC, return type changes to `Iterator[str]` — pure abstract, still no implementation |
| Adapters: implement contracts, contain I/O | ✅ | Thread + Queue bridge in `CliContainerManager` (adapter layer). `on_output` callback receives `bytes`, decoded in adapter. |
| Adapters: orchestration only, no business logic | ✅ | Thread bridges transport output to caller — no domain logic |
| Factory: only DI composition root | ✅ Unchanged | No factory changes needed |
| No new I/O pattern | ✅ | `threading` and streaming via `on_output` are both already established in `CliTransport` |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-06-02
**Changes applied:**

1. **`ports/managers.py`** — Changed `logs()` return type from `str` to `Iterator[str]`, added `from typing import Iterator`
2. **`adapters/managers/container.py`** — Rewrote `logs()` with two code paths: non-follow yields decoded stdout via `yield self._decode_stdout(result.stdout)`, follow uses `threading.Thread` + `queue.Queue` bridge converting transport's `on_output` callback pattern into an `Iterator[str]`. Added `from queue import Queue`, `from threading import Thread`, `from typing import Iterator`
3. **`tests/helpers/mock_transport.py`** — Added `stream_responses` dict to `RecordingTransport`; streaming path in `execute()` calls `on_output` for each chunk when `stream=True` and a matching stream response key is found
4. **`tests/unit/ports/test_container_manager_contract.py`** — Renamed `test_logs_returns_str` to `test_logs_returns_iterator`, changed assertion from `isinstance(result, str)` to `isinstance(result, Iterator)`
5. **`tests/integration/integration/test_manager_commands.py`** — Updated `test_logs` to use `"".join(mgr.logs("ctr1"))`, updated `test_logs_follow_tail` to use `list(mgr.logs(...))` with `stream_responses`, added `test_logs_follow_streams_chunks` validating thread + Queue bridge yields chunks in order
6. **`tests/integration/functional/test_workflows.py`** — Updated `test_container_logs_with_options` to use `stream_responses` and `"".join(...)`, updated `test_container_lifecycle` to use `"".join(mgr.logs("ctr1"))`
7. **`tests/integration/boundary/test_empty_outputs.py`** — Updated `test_logs_empty` to use `"".join(mgr.logs("ctr1"))`
8. **`tests/integration/smoke/test_real_runtime.py`** — Updated log assertion to use `"".join(...)`

**Solution rationale:** Changed `logs()` return type from `str` to `Iterator[str]` so the return type honestly represents both fetch (finite) and stream (infinite) cases. Non-follow yields the full decoded stdout as a single chunk and exhausts immediately. Follow uses a `threading.Thread` + `queue.Queue` bridge — the background thread calls `Transport.execute(cmd, stream=True, on_output=callback)`, the callback decodes each chunk via `self._decode_stdout()` and puts it in the queue, and the main thread yields from the queue. Errors from the background thread are stored and re-raised when the iterator exhausts. This reuses three established patterns: `Transport.execute(stream=True, on_output=...)`, `threading.Thread` (already used in `CliTransport`), and `self._decode_stdout()` from `CliBaseManager`.

**Verification:** 613 tests pass (0 failures) across unit and integration suites.

#### 1. The Contract

`ports/transport.py:7-10` defines `ExecResult`:
```python
@dataclass
class ExecResult:
    returncode: int
    stdout: bytes
    stderr: bytes
```

`ports/managers.py:92` and `ports/managers.py:112` define the abstract contracts:
```python
class VolumeManager(ABC):
    def create(self, name: str, ...) -> str: ...   # returns str

class NetworkManager(ABC):
    def create(self, name: str, ...) -> str: ...   # returns str
```

The `Transport` ABC (`ports/transport.py:13-24`) declares `execute()` returning `ExecResult` with `stdout: bytes`. This is **correct** — the transport is encoding-agnostic raw I/O. The manager is responsible for decoding.

#### 2. All `result.stdout` Usages in the Source Tree

Every place `result.stdout` is consumed across all 4 managers + engine:

| File | Line | Current Code | Returns/Passes |
|------|------|-------------|----------------|
| `volume.py` | 20 | `result.stdout.strip()` | `bytes` 🔴 |
| `volume.py` | 40 | `self._parser.parse_inspect(result.stdout)` | `bytes` 🔴 |
| `volume.py` | 51 | `self._parser.parse_list(result.stdout)` | `bytes` 🔴 |
| `volume.py` | 56 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `network.py` | 20 | `result.stdout.strip()` | `bytes` 🔴 |
| `network.py` | 50 | `self._parser.parse_inspect(result.stdout)` | `bytes` 🔴 |
| `network.py` | 61 | `self._parser.parse_list(result.stdout)` | `bytes` 🔴 |
| `network.py` | 66 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `container.py` | 95 | `result.stdout.decode("utf-8", errors="replace").strip()` | `str` ✅ |
| `container.py` | 132 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `container.py` | 145 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `container.py` | 155 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `container.py` | 167 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `container.py` | 172 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `image.py` | 50 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `image.py` | 72 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `image.py` | 92 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `image.py` | 103 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `image.py` | 110 | `result.stdout.decode("utf-8", errors="replace")` | `str` ✅ |
| `engine/cli.py` | 65 | `result.stdout.decode("utf-8", errors="replace").strip()` | `str` ✅ |
| `engine/cli.py` | 80 | `result.stdout.decode("utf-8", errors="replace").strip()` | `str` ✅ |

Key observation: **Volume and network managers decode correctly in `prune()` but NOT in `create()`/`inspect()`/`list()`** — inconsistency within the same two files strongly suggests oversight, not design.

#### 3. Git History Investigation

Three commits touch these files:

| Commit | Message | What Changed |
|--------|---------|-------------|
| `09a8c9c` | *"feat: stabilize oci-runtime with bytes-safe transport and context-aware errors"* | Original implementation. Container/image already had `.decode()`. Volume/network used raw `bytes.strip()`. |
| `423ee5a` | *"refactor(oci-runtime): instance factory with explicit RuntimePreference + DI"* | Factory restructure. Manager code unchanged. |
| `5118502` | *"fixes based on oci-runtime-audit-report.md"* | **Latest commit.** Fixed `prune()` — replaced fake hardcoded dicts (`{"deleted": 1, "space_reclaimed": 0}`) with real parser calls using `.decode()`. But **missed** `create()`/`inspect()`/`list()`. |

The diff of commit `5118502` for `volume.py`:
```diff
-        self._transport.execute(cmd)
-        return {"deleted": 1, "space_reclaimed": 0}
+        result = self._transport.execute(cmd)
+        return self._parser.parse_prune(result.stdout.decode("utf-8", errors="replace"))
```

The same pattern was applied to `network.py`. The author fixed `prune()` with proper decoding but did not fix the other three methods in the same files.

Additionally, the original `BaseManager` (with `_check_result`) lived in **`ports/managers.py`** (ports layer — architecture violation). Commit `5118502` extracted it into **`adapters/managers/base.py`** as `CliBaseManager` (correct adapters layer), proving ongoing architectural cleanup.

#### 4. Crash Scenarios for Downstream Callers

When a caller receives `bytes` instead of `str` from `volume.create()` or `network.create()`:

| Operation | Code | Result |
|-----------|------|--------|
| f-string | `f"Volume {name} created"` | `"Volume b'myvol' created"` — `b''` prefix leaks |
| `.startswith()` | `name.startswith("test-")` | `TypeError: startswith first arg must be bytes or a tuple of bytes, not str` |
| Concatenation | `"prefix-" + name` | `TypeError: can only concatenate str (not "bytes") to str` |
| `.replace()` | `name.replace("vol", "volume")` | `TypeError: a bytes-like object is required, not 'str'` |

#### 5. Callers Across the Codebase

| File | Line | Usage | Impact |
|------|------|-------|--------|
| `test_real_runtime.py` | 73 | `name = engine.volumes.create(vol_name)` then `name.strip()` | Works on bytes too — masks bug |
| `test_real_runtime.py` | 82 | `name = engine.networks.create(net_name)` then `name.strip()` | Works on bytes too — masks bug |
| `test_workflows.py` | 214 | `assert name == b"myvol"` | **Expects bytes! Will break when fixed** |
| `test_workflows.py` | 233 | `docker_engine.volumes.create(...)` — return discarded | No impact |
| `test_workflows.py` | 260 | `assert name == b"mynet"` | **Expects bytes! Will break when fixed** |
| `test_workflows.py` | 276 | `docker_engine.networks.create(...)` — return discarded | No impact |

#### 6. Parsers — Why `bytes` Works Accidentally (Finding #2 Connection)

All `parse_inspect()` and `parse_list()` methods call `json.loads(raw)` internally. Python 3.6+ `json.loads()` accepts `bytes` natively, so passing `bytes` instead of `str` works at runtime — but violates the type contract (`raw: str`).

Methods that do **not** tolerate bytes:
- `parse_size_to_bytes()` uses `size_str.upper()` → `AttributeError: 'bytes' object has no attribute 'upper'`
- `BaseCliParser.parse_prune()` uses `re.compile(...).findall(raw)` — regex on bytes returns `bytes` matches instead of `str` matches
- `is_not_found_error()` uses `in stderr` — but stderr is always decoded by `_check_result` in `base.py:42`

Fortunately, `parse_prune()` is only called from `prune()` methods (which already decode correctly in all 4 managers). The volume/network `inspect()` and `list()` methods happen to work because `json.loads()` accepts bytes — this is a latent bug.

---

### Prototype Validation

**File:** `dev/validation/oci_runtime/finding-1-decode-stdout-approach.py`

A standalone Python script was created to validate the approach end-to-end.

#### Prototype Architecture

The script simulates the full layer stack:
1. `ExecResult` dataclass (same as `ports/transport.py`)
2. `CliBaseManager` with `_decode_stdout()` method (proposed fix location)
3. `BuggyVolumeManager`/`BuggyNetworkManager` — current broken implementation
4. `FixedVolumeManager`/`FixedNetworkManager` — proposed fixed implementation
5. `FixedContainerManager`/`FixedImageManager` — refactored to use helper
6. Simplified parsers (`VolumeParser`, `NetworkParser`) — same `json.loads()` logic
7. Domain types (`VolumeInfo`, `NetworkInfo`) — simplified dataclasses
8. Non-UTF-8 edge case simulation (`b"valid_name\xff\xfe"`)

#### Prototype Results (Full Output)

```
========================================================================
PROTOTYPE: _decode_stdout approach for Finding #1
========================================================================

─── 1. CURRENT BUG: volume/network create() returns bytes ───

  volume.create() returns type: bytes
  volume.create() returns value: b'myvol'
  f-string: f'Volume b'myvol' created' -> "Volume b'myvol' created"

  network.create() returns type: bytes
  network.create() returns value: b'mynet'
  f-string: f'Network b'mynet' created' -> "Network b'mynet' created"

  CRASH SCENARIOS with current buggy code:
    f-string:       f'Volume {name} created'
      -> 'Volume b'mynet' created'  (b'' prefix leaks)
    .startswith():  name.startswith('my')
      -> TypeError: startswith first arg must be bytes or a tuple of bytes, not str
    concatenation:  'prefix-' + name
      -> TypeError: can only concatenate str (not "bytes") to str

─── 2. FIXED: _decode_stdout makes everything str ───

  volume.create() returns type: str
  volume.create() returns value: 'myvol'
  f-string: f'Volume myvol created' -> 'Volume myvol created'
  .startswith('my'):            True
  'prefix-' + name:             'prefix-myvol'

  network.create() returns type: str
  network.create() returns value: 'mynet'
  f-string: f'Network mynet created' -> 'Network mynet created'

─── 3. Parser compatibility (json.loads with str vs bytes) ───

  Buggy: parse_inspect(result.stdout) [bytes]  -> name=myvol (works but type hint lies)
  Fixed: parse_inspect(_decode_stdout(...)) [str] -> name=myvol
  json.loads(bytes) works: [{'Name': 'vol1', 'Driver': 'local'}]
  json.loads(str)    works: [{'Name': 'vol1', 'Driver': 'local'}]
  raw_str.startswith('['):         True
  raw_bytes.startswith('['):        TypeError: startswith first arg must be bytes or a tuple of bytes, not str

─── 4. Edge case: non-UTF-8 output ───

  Input bytes: b'valid_volume_name\xff\xfe'
  Decoded str: 'valid_volume_name��'
  (errors='replace' substitutes bad bytes with U+FFFD)
  .strip() works: 'valid_volume_name��'
  No crash: ✅

─── 5. All 4 managers use same _decode_stdout ───

  ContainerManager.run():    type=str, val='abc123'
  ContainerManager.inspect(): type=str
  ImageManager.build():       type=str, val='sha256:abc123\n'
  VolumeManager.create():     type=str, val='myvol'
  NetworkManager.create():    type=str, val='mynet'
```

#### What the Prototype Validates

| Check | Result | Evidence |
|-------|--------|----------|
| Bug is real | ✅ Confirmed | `type(bytes)` returned, `.startswith()` crashes, f-string leaks `b''` |
| Fix returns str | ✅ Confirmed | `type(str)` returned, all string ops work |
| Non-UTF-8 safe | ✅ Confirmed | `errors='replace'` substitutes bad bytes, no crash |
| Parser compatibility | ✅ Confirmed | `json.loads()` works with both bytes and str |
| All 4 managers consistent | ✅ Confirmed | Same helper call pattern in every method |
| `.strip()` after decode | ✅ Confirmed | `self._decode_stdout(result.stdout).strip()` works correctly |

---

### Proposed Solution

#### Approach: `_decode_stdout()` helper in `CliBaseManager`

Instead of adding raw `.decode()` calls to every method (the current pattern in container/image), extract a reusable helper method in the shared base class. This is consistent with `_resolve_val()` and `_check_result()` which already live in `CliBaseManager`.

**Add to** `adapters/managers/base.py`:
```python
def _decode_stdout(self, data: bytes) -> str:
    """Decode raw bytes from transport to string.

    The transport layer (I/O boundary) returns bytes. The manager
    (orchestration layer) decodes to str before passing to parsers
    or returning to callers.

    Uses errors='replace' for robustness against non-UTF-8 output
    without crashing.
    """
    return data.decode("utf-8", errors="replace")
```

#### Then fix each affected method:

**`volume.py`** (3 sites):
- Line 20: `result.stdout.strip()` → `self._decode_stdout(result.stdout).strip()`
- Line 40: `self._parser.parse_inspect(result.stdout)` → `self._parser.parse_inspect(self._decode_stdout(result.stdout))`
- Line 51: `self._parser.parse_list(result.stdout)` → `self._parser.parse_list(self._decode_stdout(result.stdout))`

**`network.py`** (3 sites):
- Line 20: `result.stdout.strip()` → `self._decode_stdout(result.stdout).strip()`
- Line 50: `self._parser.parse_inspect(result.stdout)` → `self._parser.parse_inspect(self._decode_stdout(result.stdout))`
- Line 61: `self._parser.parse_list(result.stdout)` → `self._parser.parse_list(self._decode_stdout(result.stdout))`

**`container.py`** (6 sites, refactor to use helper):
- Line 95: `result.stdout.decode("utf-8", errors="replace").strip()` → `self._decode_stdout(result.stdout).strip()`
- Line 132: `result.stdout.decode("utf-8", errors="replace")` → `self._decode_stdout(result.stdout)`
- Line 145: same
- Line 155: same
- Line 167: same
- Line 172: same

**`image.py`** (5 sites, refactor to use helper):
- Line 50: `result.stdout.decode("utf-8", errors="replace")` → `self._decode_stdout(result.stdout)`
- Line 72: same
- Line 92: same
- Line 103: same
- Line 110: same

#### Tests to update

**`test_workflows.py:214`**: `assert name == b"myvol"` → `assert name == "myvol"`
**`test_workflows.py:260`**: `assert name == b"mynet"` → `assert name == "mynet"`

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Domain: pure Python, no I/O | ✅ Unchanged | Domain types not modified |
| Ports: ABCs only, no implementation | ✅ Unchanged | `ExecResult.stdout: bytes` preserved in port |
| Adapters: implement contracts, contain I/O | ✅ | `_decode_stdout` in `CliBaseManager` (adapter layer) |
| Factory: only place wiring ports to adapters | ✅ Unchanged | No factory changes needed |

The fix respects the clean architecture:
- Transport (port) remains encoding-agnostic → `stdout: bytes`
- `CliBaseManager` (adapter) provides the decode helper → correct I/O boundary layer
- Each manager (adapter) uses the helper → orchestration responsibility
- Parsers (adapter) receive `str` → type contract satisfied

#### Alternative Considered: Change `ExecResult.stdout` to `str`

Changing `ExecResult.stdout` from `bytes` to `str` and decoding in `CliTransport.execute()` was considered but rejected:

| Pro | Con |
|-----|-----|
| Single decode point (DRY) | Transport would assume encoding (violates I/O boundary purity) |
| Simpler manager code | Streaming `on_output` callback takes `bytes` — path mismatch |
| No per-method changes | Would require `CliTransport` to decode all output upfront |

The `on_output: Callable[[bytes], None]` callback in the transport's streaming path receives raw bytes for real-time output processing. If `ExecResult.stdout` were `str`, the streaming accumulator would need to decode bytes and re-encode them for the callback — or change the callback signature, breaking the port contract.

**Verdict**: The `_decode_stdout` helper approach is architecturally superior to changing the transport return type.

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-05-29
**Changes applied:**

1. **`adapters/managers/base.py`** — Added `_decode_stdout(data: bytes) -> str` to `CliBaseManager`
2. **`adapters/managers/volume.py`** — Fixed 3 sites: `create()`, `inspect()`, `list()` now decode before returning/passing to parsers
3. **`adapters/managers/network.py`** — Fixed 3 sites: `create()`, `inspect()`, `list()` now decode before returning/passing to parsers
4. **`adapters/managers/container.py`** — Refactored 6 sites to use `_decode_stdout` helper
5. **`adapters/managers/image.py`** — Refactored 5 sites to use `_decode_stdout` helper
6. **`tests/unit/adapters/test_cli_volume_manager.py`** — Added `test_create_returns_str`, `test_list_returns_list_of_volume_info`, `test_inspect_returns_volume_info`, `test_decode_stdout_converts_bytes_to_str`, `test_decode_stdout_handles_non_utf8`, `test_decode_stdout_strip_preserved`
7. **`tests/unit/adapters/test_cli_network_manager.py`** — Added `test_create_returns_str`, `test_list_returns_list_of_network_info`, `test_inspect_returns_network_info`
8. **`tests/integration/functional/test_workflows.py`** — Updated 2 byte-string assertions to str
9. **`tests/integration/integration/test_manager_commands.py`** — Updated 2 byte-string assertions to str

**Solution rationale:** Extracted `_decode_stdout()` helper in `CliBaseManager` (adapters layer) rather than changing the transport return type (ports layer). This preserves hexagonal architecture: transport remains encoding-agnostic (`stdout: bytes`), managers decode before returning to callers or passing to parsers. See the full investigation above for why this approach was chosen over alternatives.

**Verification:** 484 tests pass (0 failures) across unit and integration suites.

---

### Finding #2: Volume/Network `inspect()` and `list()` Pass `bytes` to `str`-Typed Parsers [RESOLVED]

**Files:** `adapters/managers/volume.py:40,51`, `adapters/managers/network.py:50,61`

**Code:**
```python
# volume.py line 40 — passes bytes to parser typed with raw: str
info = self._parser.parse_inspect(result.stdout)

# volume.py line 51 — same issue
return self._parser.parse_list(result.stdout)

# network.py line 50 — same issue
info = self._parser.parse_inspect(result.stdout)

# network.py line 61 — same issue
return self._parser.parse_list(result.stdout)
```

**Problem:** Parser methods (`parse_inspect`, `parse_list`) are typed with `raw: str` parameters. Volume and network managers pass raw `result.stdout` (bytes) directly. This works today because `json.loads()` accepts `bytes` in Python 3.6+, but it breaks silently on any string-only operation (`.startswith()`, `.split()`, regex, string formatting).

**Contrast with correct pattern:** `CliContainerManager.inspect()` (container.py:132) and `CliImageManager.inspect()` (image.py:92) both call `.decode("utf-8", errors="replace")` before passing to parsers.

**Root cause:** Same as Finding #1 — volume and network managers skip the `.decode()` step. The `prune()` methods in the same two files correctly decode (`volume.py:56`, `network.py:66`), but `inspect()` and `list()` do not.

**Detection gap:** No test asserts the type of data reaching parsers. The type hint violation is invisible at runtime because `json.loads(bytes)` happens to work.

---

### Deep Investigation — Why It Works Accidentally and What Breaks

#### 1. The Parser Contract

All parser `parse_inspect()` and `parse_list()` methods are typed with `raw: str`:

```python
# ports/parsers.py
class VolumeParser(ABC):
    def parse_inspect(self, raw: str) -> VolumeInfo | None: ...
    def parse_list(self, raw: str) -> list[VolumeInfo]: ...

class NetworkParser(ABC):
    def parse_inspect(self, raw: str) -> NetworkInfo | None: ...
    def parse_list(self, raw: str) -> list[NetworkInfo]: ...
```

The implementations call `json.loads(raw)` internally. Python 3.6+ `json.loads()` accepts both `str` and `bytes`, so the type violation is never caught at runtime — until a string-only operation is used.

#### 2. Operations That Crash on `bytes`

| Operation | Code | Result with `bytes` | Result with `str` |
|-----------|------|---------------------|--------------------|
| `json.loads()` | `json.loads(data)` | ✅ Works (by accident) | ✅ Works |
| `.startswith(str)` | `data.startswith("[")` | ❌ `TypeError` | ✅ `True` |
| `.replace(str, str)` | `data.replace("x", "y")` | ❌ `TypeError` | ✅ Works |
| `re.search(str)` | `re.search(r"pattern", data)` | ❌ Requires `bytes` pattern | ✅ Works |
| `in` operator | `"key" in data` | ❌ `TypeError` | ✅ Works |
| String concatenation | `"prefix-" + data` | ❌ `TypeError` | ✅ Works |

#### 3. Full Source Trace: All `result.stdout` Passed to Parsers

| File | Line | Call | Type Passed | Correct? |
|------|------|------|-------------|----------|
| `volume.py` | 40 | `self._parser.parse_inspect(result.stdout)` | `bytes` | 🔴 |
| `volume.py` | 51 | `self._parser.parse_list(result.stdout)` | `bytes` | 🔴 |
| `network.py` | 50 | `self._parser.parse_inspect(result.stdout)` | `bytes` | 🔴 |
| `network.py` | 61 | `self._parser.parse_list(result.stdout)` | `bytes` | 🔴 |
| `container.py` | 132 | `self._parser.parse_inspect(result.stdout.decode(...))` | `str` | ✅ |
| `container.py` | 145 | `self._parser.parse_list(result.stdout.decode(...))` | `str` | ✅ |
| `image.py` | 92 | `self._parser.parse_inspect(result.stdout.decode(...))` | `str` | ✅ |
| `image.py` | 103 | `self._parser.parse_list(result.stdout.decode(...))` | `str` | ✅ |

#### 4. Crash Scenarios for Future Code Changes

If a parser method ever calls a string-only operation (e.g., `.startswith()` to detect JSON array formatting, `.split()` for custom parsing, or `re.search()` with a `str` pattern), the bug surfaces as a `TypeError` at runtime:

```python
# Hypothetical future parser change:
def parse_inspect(self, raw: str) -> VolumeInfo | None:
    if raw.startswith("["):    # ✅ works with str, ❌ TypeError with bytes
        data = json.loads(raw)
        ...
```

This is a time bomb in the parser code path.

---

### Prototype Validation

**File:** `dev/validation/oci_runtime/finding-2-validate-parser-bytes-fix.py`

A standalone Python script validates the bug and fix end-to-end with 8 tests.

#### Prototype Architecture

1. `ExecResult` dataclass — same as `ports/transport.py`
2. `VolumeParser` / `NetworkParser` — simplified parsers matching real contracts
3. `BuggyVolumeManager` / `BuggyNetworkManager` — current broken implementation (passes bytes)
4. `FixedVolumeManager` / `FixedNetworkManager` — proposed fix (decodes before passing)
5. `CliBaseManager._decode_stdout()` — the proposed helper
6. String operation edge cases — `.startswith()`, `.replace()`, regex, non-UTF-8

#### Prototype Results (Full Output)

```
========================================================================
PROTOTYPE: Validate Finding #2 fix (bytes->str for parsers)
========================================================================

Test                                               Result
------------------------------------------------------------------------
Buggy code accidentally works                        PASS
  -> Buggy code works by accident (json.loads accepts bytes)

Buggy code passes bytes to parsers                   PASS
  -> Buggy code passes bytes to parsers: vol_inspect=bytes,
     vol_list=bytes, net_inspect=bytes, net_list=bytes

Fixed code passes str to parsers                     PASS
  -> Fixed code passes str to parsers: vol_inspect=str,
     vol_list=str, net_inspect=str, net_list=str

String ops crash on bytes (latent bug)               PASS
  -> json.loads(bytes) works by accident.
     startswith/replace crash on bytes.
     regex returns bytes matches.

String ops work with str (fix)                       PASS
  -> All string operations work with str input

Parser results correct with fix                      PASS
  -> All parser results correct: volume.inspect,
     volume.list, network.inspect, network.list

Consistent with container/image pattern              PASS
  -> All 4 managers use consistent decode-before-parse pattern

Non-UTF-8 edge case                                  PASS
  -> Non-UTF-8 handled with replacement:
     name='valid_volume_name��'

========================================================================
RESULT: ALL TESTS PASSED
=> The _decode_stdout fix resolves Finding #2 (and Finding #1)
========================================================================
```

#### What the Prototype Validates

| Check | Result | Evidence |
|-------|--------|----------|
| Bug is real | ✅ Confirmed | 4/4 manager methods pass `bytes` to parsers |
| Works by accident | ✅ Confirmed | `json.loads(bytes)` silently succeeds |
| Latent crash risk | ✅ Confirmed | `.startswith()` and `.replace()` raise `TypeError` on `bytes` |
| Fix passes `str` | ✅ Confirmed | All 4 fixed methods pass `str` to parsers |
| Parser results correct | ✅ Confirmed | `inspect()` and `list()` return correct domain data |
| Non-UTF-8 safe | ✅ Confirmed | `errors='replace'` substitutes bad bytes |
| Consistent with container/image | ✅ Confirmed | Same `_decode_stdout` call pattern |

---

### Proposed Solution

#### Approach: Combined fix with Finding #1 — `_decode_stdout()` helper

Finding #2 is directly resolved by the same fix as Finding #1. The `_decode_stdout()` helper in `CliBaseManager` decodes bytes to str before data reaches parsers.

**Add to** `adapters/managers/base.py`:
```python
def _decode_stdout(self, data: bytes) -> str:
    return data.decode("utf-8", errors="replace")
```

**Then fix each affected method:**

**`volume.py`** (2 sites for Finding #2, 3 total with Finding #1):
- Line 40: `self._parser.parse_inspect(result.stdout)` → `self._parser.parse_inspect(self._decode_stdout(result.stdout))`
- Line 51: `self._parser.parse_list(result.stdout)` → `self._parser.parse_list(self._decode_stdout(result.stdout))`
- (Line 20: `result.stdout.strip()` → `self._decode_stdout(result.stdout).strip()` — Finding #1)

**`network.py`** (2 sites for Finding #2, 3 total with Finding #1):
- Line 50: `self._parser.parse_inspect(result.stdout)` → `self._parser.parse_inspect(self._decode_stdout(result.stdout))`
- Line 61: `self._parser.parse_list(result.stdout)` → `self._parser.parse_list(self._decode_stdout(result.stdout))`
- (Line 20: `result.stdout.strip()` → `self._decode_stdout(result.stdout).strip()` — Finding #1)

#### Tests to Update

**`test_workflows.py:214`**: `assert name == b"myvol"` → `assert name == "myvol"`
**`test_workflows.py:260`**: `assert name == b"mynet"` → `assert name == "mynet"`

Both tests currently expect `bytes` return values. After the fix, `create()` returns `str`.

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Domain: pure Python, no I/O | ✅ Unchanged | Domain types not modified |
| Ports: ABCs only, no implementation | ✅ Unchanged | Parser `raw: str` contract unchanged |
| Adapters: implement contracts, contain I/O | ✅ | `_decode_stdout` in `CliBaseManager` (adapter layer) |
| Factory: only place wiring ports to adapters | ✅ Unchanged | No factory changes needed |

The fix respects the clean architecture:
- Transport (port) returns bytes → encoding-agnostic I/O boundary
- `CliBaseManager` (adapter) decodes bytes to str → correct boundary layer
- Parsers (adapter) receive `str` → type contract satisfied

**Status:** ✅ RESOLVED — Fixed together with Finding #1 via `_decode_stdout` helper. The `parse_inspect()` and `parse_list()` calls in volume/network managers now receive decoded `str` instead of raw `bytes`.

---

## 🟠 HIGH-SEVERITY ISSUES

### Finding #3: Duplicate `BaseCliParser` and `parse_size_to_bytes` (DRY Violation) [RESOLVED]

**Files:** `adapters/parser/docker.py:19-56`, `adapters/parser/podman.py:19-56`

**Code (identical block in both files):**
```python
def parse_size_to_bytes(size_str: str) -> int:
    """Helper to convert strings like '1.24GB' or '512MB' to bytes."""
    units = {
        'B': 1,
        'KB': 1024,
        'MB': 1024**2,
        'GB': 1024**3,
        'TB': 1024**4,
        'KIB': 1024,
        'MIB': 1024**2,
        'GIB': 1024**3,
    }
    match = re.search(r"(\d+\.?\d*)\s*([a-zA-Z]+)", size_str.upper())
    if not match:
        return 0
    number, unit = match.groups()
    return int(float(number) * units.get(unit, 1))


class BaseCliParser:
    """Shared logic for CLI parsers."""
    def parse_prune(self, raw: str) -> dict[str, int]:
        deleted_count = 0
        reclaimed_bytes = 0

        id_pattern = re.compile(r"^[a-f0-9]{12,64}$", re.MULTILINE)
        deleted_count = len(id_pattern.findall(raw))

        space_match = re.search(r"Total reclaimed space:\s*(.*)", raw, re.IGNORECASE)
        if space_match:
            reclaimed_bytes = parse_size_to_bytes(space_match.group(1))

        return {
            "deleted": deleted_count,
            "reclaimed_bytes": reclaimed_bytes
        }
```

**Problem:** 38 lines of identical code (`parse_size_to_bytes()` function + `BaseCliParser` class with `parse_prune()`) are copy-pasted across both `docker.py` and `podman.py`. Any bug fix, enhancement, or refactoring must be applied identically in two places. This is a textbook DRY violation.

**Root cause:** Both parser modules independently needed the same utility function and base class. Instead of extracting a shared module, the code was duplicated at implementation time.

**Detection gap:** No linting rule or review process caught the duplication. The identical blocks diverge only by accident — any future change to one file's block without updating the other creates a subtle behavioral difference between Docker and Podman parsing paths.

---

### Deep Investigation — Full Source Trace

#### 1. The Duplicate Source Trace

Every line of `parse_size_to_bytes()` and `BaseCliParser` is byte-identical between the two files:

| Function/Class | docker.py Line | podman.py Line | Identical? |
|---------------|----------------|----------------|------------|
| `parse_size_to_bytes` | 19–35 | 19–35 | ✅ Identical |
| `BaseCliParser.parse_prune` | 38–56 | 38–56 | ✅ Identical |
| Docstring | 20 | 20 | ✅ Identical |
| `units` dict | 21–30 | 21–30 | ✅ Identical |
| `re.search` pattern | 31 | 31 | ✅ Identical |
| `id_pattern` regex | 45 | 45 | ✅ Identical |
| `space_match` regex | 49 | 49 | ✅ Identical |

#### 2. DRY Analysis — Maintenance Burden

| Scenario | With Duplication | With Single Source |
|----------|-----------------|-------------------|
| Fix regex bug in `parse_size_to_bytes` | 2 files to edit, test | 1 file to edit, test |
| Add new unit (e.g. `PB`/`EB`) | 2 files | 1 file |
| Change `parse_prune` output format | 2 files | 1 file |
| Add new shared parser utility method | 2 files (likely missed) | 1 file |

#### 3. MRO Chain Analysis

All 8 concrete parser classes use multiple inheritance: `(BaseCliParser, ContainerParser)` (or Image/Volume/Network equivalents). The `parse_prune()` method is declared as `@abstractmethod` on all 4 port ABCs (`ContainerParser`, `ImageParser`, `VolumeParser`, `NetworkParser`), and `BaseCliParser` provides the concrete implementation.

With the current duplication, each runtime's parsers resolve `parse_prune()` from their own local `BaseCliParser`. After extraction, all 8 classes resolve from the single `BaseCliParser` in `base.py` — which is functionally identical but avoids the DRY violation.

---

### Prototype Validation

**File:** `dev/validation/oci_runtime/finding-3-extract-base-parser.py`

A standalone Python script validates the extraction end-to-end with comprehensive tests.

#### Prototype Results

```
PROTOTYPE: Extract BaseCliParser + parse_size_to_bytes to base.py

─── 1. parse_size_to_bytes() from base module ───
  PASS   | GB parsing
  PASS   | MB parsing
  PASS   | No unit returns 0
  PASS   | Space in string handled
  PASS   | Empty string returns 0

─── 2. BaseCliParser.parse_prune() ───
  PASS   | Counts hex IDs
  PASS   | Parses reclaimed space
  PASS   | Empty input returns zeros
  PASS   | Multiple IDs counted

─── 3. Docker parsers (using BaseCliParser from base) ───
  PASS   | DockerContainerParser.parse_inspect
  PASS   | DockerContainerParser.parse_prune (inherited)
  PASS   | DockerImageParser.parse_inspect
  PASS   | DockerVolumeParser.parse_inspect
  PASS   | DockerNetworkParser.parse_inspect

─── 4. Podman parsers (using BaseCliParser from base) ───
  PASS   | PodmanContainerParser.parse_inspect
  PASS   | PodmanContainerParser.parse_prune (inherited)
  PASS   | PodmanImageParser.parse_inspect
  PASS   | PodmanVolumeParser.parse_inspect
  PASS   | PodmanNetworkParser.parse_inspect

─── 5. MRO integrity ───
  PASS   | DockerContainerParser inherits parse_prune from BaseCliParser
  PASS   | DockerImageParser inherits parse_prune from BaseCliParser
  PASS   | DockerVolumeParser inherits parse_prune from BaseCliParser
  PASS   | DockerNetworkParser inherits parse_prune from BaseCliParser
  PASS   | PodmanContainerParser inherits parse_prune from BaseCliParser
  PASS   | PodmanImageParser inherits parse_prune from BaseCliParser
  PASS   | PodmanVolumeParser inherits parse_prune from BaseCliParser
  PASS   | PodmanNetworkParser inherits parse_prune from BaseCliParser

─── 6. Module-level re-export compatibility ───
  PASS   | Re-exported parse_size_to_bytes works

RESULTS: 23 PASSED, 0 FAILED
```

#### What the Prototype Validates

| Check | Result | Evidence |
|-------|--------|----------|
| `parse_size_to_bytes` works from base module | ✅ Confirmed | All unit conversions correct |
| `BaseCliParser.parse_prune` works from base module | ✅ Confirmed | ID counting, space parsing, empty input |
| Docker parsers work with extracted base | ✅ Confirmed | All 4 Docker parsers functional |
| Podman parsers work with extracted base | ✅ Confirmed | All 4 Podman parsers functional |
| MRO resolves `parse_prune` from `BaseCliParser` | ✅ Confirmed | All 8 concrete classes |
| Module-level re-export compatibility | ✅ Confirmed | Legacy import paths still work |

---

### Proposed Solution

#### Approach: Extract to `adapters/parser/base.py`

Create a new shared module `base.py` in the same `adapters/parser/` directory containing the exact duplicated code. Update both `docker.py` and `podman.py` to import from the shared module instead of defining their own.

**Create** `adapters/parser/base.py`:
```python
import re

def parse_size_to_bytes(size_str: str) -> int:
    """Helper to convert strings like '1.24GB' or '512MB' to bytes."""
    units = {
        'B': 1,
        'KB': 1024,
        'MB': 1024**2,
        'GB': 1024**3,
        'TB': 1024**4,
        'KIB': 1024,
        'MIB': 1024**2,
        'GIB': 1024**3,
    }
    match = re.search(r"(\d+\.?\d*)\s*([a-zA-Z]+)", size_str.upper())
    if not match:
        return 0
    number, unit = match.groups()
    return int(float(number) * units.get(unit, 1))


class BaseCliParser:
    """Shared logic for CLI parsers."""
    def parse_prune(self, raw: str) -> dict[str, int]:
        deleted_count = 0
        reclaimed_bytes = 0

        id_pattern = re.compile(r"^[a-f0-9]{12,64}$", re.MULTILINE)
        deleted_count = len(id_pattern.findall(raw))

        space_match = re.search(r"Total reclaimed space:\s*(.*)", raw, re.IGNORECASE)
        if space_match:
            reclaimed_bytes = parse_size_to_bytes(space_match.group(1))

        return {
            "deleted": deleted_count,
            "reclaimed_bytes": reclaimed_bytes
        }
```

**Update** `adapters/parser/docker.py` — Remove lines 19–56, add at top:
```python
from oci_runtime.adapters.parser.base import BaseCliParser, parse_size_to_bytes
```

**Update** `adapters/parser/podman.py` — Same change: remove lines 19–56, add same import.

#### Tests Added

**`tests/unit/adapters/test_parser_base.py`** — 9 new tests:
- `TestParseSizeToBytes` (6 tests): GB, MB, KB, empty string, no unit, spaced input
- `TestBaseCliParser` (3 tests): deleted count, reclaimed space, empty input

**No existing test changes required** — No test imports `parse_size_to_bytes` or `BaseCliParser` directly. All 8 concrete parser classes inherit from `BaseCliParser` via MRO, and the extraction does not change the MRO chain.

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Domain: pure Python, no I/O | ✅ Unchanged | No domain types modified |
| Ports: ABCs only, no implementation | ✅ Unchanged | `parse_prune` remains abstract on all 4 port ABCs |
| Adapters: implement contracts, contain I/O | ✅ | `base.py` is in `adapters/parser/` — same adapter layer as `docker.py`/`podman.py` |
| Factory: only DI composition root | ✅ Unchanged | Factory imports concrete classes from `docker.py`/`podman.py`, not `base.py` |

The extraction is entirely within the adapter layer. `BaseCliParser` is an adapter implementation detail fulfilling the `parse_prune()` contract declared by port ABCs. No port or domain code is touched.

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-05-30
**Changes applied:**

1. **`adapters/parser/base.py`** — Created with `parse_size_to_bytes()` function and `BaseCliParser` class with `parse_prune()`
2. **`adapters/parser/docker.py`** — Removed 38 duplicate lines (lines 19–56), added import from base module
3. **`adapters/parser/podman.py`** — Removed 38 duplicate lines (lines 19–56), added import from base module
4. **`tests/unit/adapters/test_parser_base.py`** — Added 9 unit tests for the extracted module

**Validation:** 503/503 tests pass (0 failures, 9 new tests). Smoke-tested all 8 concrete parser classes — `parse_inspect`, `parse_list`, `parse_prune`, `is_not_found_error`, and runtime-specific methods (`parse_build_output`, `parse_id_from_pull`) all work correctly. MRO verified: all 8 classes inherit `parse_prune` from `BaseCliParser` (not from port ABCs).

**DRY impact:** 38 lines × 2 files = 76 lines of duplicate code eliminated → single source of truth.

**Validation scripts:** `dev/validation/oci_runtime/finding-3-run.sh` (full test suite validation), `dev/validation/oci_runtime/finding-3-extract-base-parser.py` (initial prototype).

### Finding #4: `build_parsers` and `build_capabilities` Have Silent Fallbacks [RESOLVED]

**File:** `factory.py:42,74`

**Code (build_capabilities, line 42):**
```python
if profile.kind == RuntimeKind.DOCKER:
    ...
if profile.kind == RuntimeKind.PODMAN:
    ...
return RuntimeCapabilities(supported_output_formats=["json"])  # silent fallback
```

**Code (build_parsers, line 74):**
```python
if profile.kind == RuntimeKind.DOCKER:
    ...
if profile.kind == RuntimeKind.PODMAN:
    ...
return build_parsers(EngineProfile(binary="", kind=RuntimeKind.DOCKER))  # recursive Docker fallback
```

**Problem:** Both functions silently handle unknown runtime kinds:
- `build_capabilities` returns generic defaults (wrong `tar_entry_name`, missing `--userns=keep-id`, etc.)
- `build_parsers` recursively calls itself with `RuntimeKind.DOCKER`, silently assigning Docker-specific parsing logic to an unknown runtime with an empty binary string `""`

**The `build_parsers` fallback is especially dangerous:** It creates `EngineProfile(binary="", kind=RuntimeKind.DOCKER)` and recurses. This silently:
1. Assigns Docker parsers to any unknown runtime
2. Passes an empty binary string downstream
3. Can cause infinite recursion if the DOCKER branch itself fails

**Since `RuntimeKind` is a 2-member enum (DOCKER, PODMAN), these fallbacks are currently unreachable in production. But if a new member is added without updating these functions, behavior degrades silently instead of failing loudly.**

**Investigation — Addressed:** After deep investigation, the recursive fallback in `build_parsers` creates `EngineProfile(binary="", kind=RuntimeKind.DOCKER)` then recurses. This is a latent infinite-loop risk if the recursion stabilization condition ever breaks. The OCI-Runtime ecosystem is an open set (Docker, Podman, nerdctl, Finch, containerd — new runtimes emerge), and `RuntimeKind` will likely grow.

### Proposed Solution

#### Approach: Option B — Registry Dict Pattern

Instead of adding a simple `raise NotImplementedError` (Option A), replace the if-chains with dict-based registries. This makes the factory extensible without code modification — adding a new runtime requires only a new module + one dict entry per registry, zero if-chain edits.

The capability registry holds pre-built `RuntimeCapabilities` instances. The parser registry holds callables (preserving lazy imports) that produce the 4-parser tuple.

**Add to** `factory.py`:
```python
_CAPABILITY_REGISTRY: dict[RuntimeKind, RuntimeCapabilities] = {
    RuntimeKind.DOCKER: RuntimeCapabilities(
        supported_output_formats=["json", "yaml"],
        needs_userns_keep_id=False,
        supports_log_drivers=True,
        tar_entry_name="Dockerfile",
    ),
    RuntimeKind.PODMAN: RuntimeCapabilities(
        supported_output_formats=["json"],
        needs_userns_keep_id=True,
        supports_log_drivers=False,
        tar_entry_name="Containerfile",
        default_run_flags=["--userns=keep-id"],
    ),
}
```

#### Then replace `build_capabilities`:

```python
def build_capabilities(profile: EngineProfile | RuntimePreference) -> RuntimeCapabilities:
    try:
        return _CAPABILITY_REGISTRY[profile.kind]
    except KeyError:
        raise NotImplementedError(
            f"No capabilities registered for RuntimeKind: {profile.kind}. "
            f"Registered: {list(_CAPABILITY_REGISTRY.keys())}"
        )
```

#### Then add parser helper functions and registry:

```python
def _load_docker_parsers() -> tuple[ContainerParser, ImageParser, VolumeParser, NetworkParser]:
    from oci_runtime.adapters.parser.docker import (
        DockerContainerParser, DockerImageParser,
        DockerNetworkParser, DockerVolumeParser,
    )
    return (DockerContainerParser(), DockerImageParser(),
            DockerVolumeParser(), DockerNetworkParser())


def _load_podman_parsers() -> tuple[ContainerParser, ImageParser, VolumeParser, NetworkParser]:
    from oci_runtime.adapters.parser.podman import (
        PodmanContainerParser, PodmanImageParser,
        PodmanNetworkParser, PodmanVolumeParser,
    )
    return (PodmanContainerParser(), PodmanImageParser(),
            PodmanVolumeParser(), PodmanNetworkParser())


_PARSER_REGISTRY: dict[RuntimeKind, ...] = {
    RuntimeKind.DOCKER: _load_docker_parsers,
    RuntimeKind.PODMAN: _load_podman_parsers,
}
```

#### Then replace `build_parsers`:

```python
def build_parsers(
    profile: EngineProfile | RuntimePreference,
) -> tuple[ContainerParser, ImageParser, VolumeParser, NetworkParser]:
    try:
        return _PARSER_REGISTRY[profile.kind]()
    except KeyError:
        raise NotImplementedError(
            f"No parsers registered for RuntimeKind: {profile.kind}. "
            f"Registered: {list(_PARSER_REGISTRY.keys())}"
        )
```

#### Tests to Add/Update

**`tests/unit/adapters/test_factory.py`** — 2 new tests:
- `TestBuildCapabilities.test_unknown_kind_raises_not_implemented_error`
- `TestBuildParsers.test_unknown_kind_raises_not_implemented_error`

**`tests/integration/capability/test_capabilities.py`** — Update:
- `test_build_capabilities_unknown_kind_returns_defaults` → assert `NotImplementedError`

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Domain: pure Python, no I/O | ✅ Unchanged | `RuntimeKind` enum unchanged |
| Ports: ABCs only, no implementation | ✅ Unchanged | `RuntimeCapabilities`, parser ABCs unchanged |
| Adapters: implement contracts, contain I/O | ✅ Unchanged | All parser classes unchanged |
| Factory: still the DI composition root | ✅ | Dicts in `factory.py` — same adapter imports, same wiring |
| Factory: depends on abstractions | ✅ | Registry returns port types, not adapter internals |
| OCP: Open for extension | ✅ | Adding nerdctl = new module + 1 dict entry; zero if-chain edits |
| No silent fallbacks | ✅ | Unknown key raises `NotImplementedError` with registered keys |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-05-30
**Changes applied:**

1. **`factory.py`** — Added `_CAPABILITY_REGISTRY` dict mapping `RuntimeKind` → `RuntimeCapabilities` and `_PARSER_REGISTRY` dict mapping `RuntimeKind` → parser factory callables. Replaced `build_capabilities` and `build_parsers` if-chains with dict lookup + `NotImplementedError` on miss. Removed silent fallback code (generic `RuntimeCapabilities` return and recursive Docker fallback).

2. **`tests/unit/adapters/test_factory.py`** — Added `_FakeRuntimeKind` helper class; added `test_unknown_kind_raises_not_implemented_error` to both `TestBuildCapabilities` and `TestBuildParsers` (2 new tests)

3. **`tests/integration/capability/test_capabilities.py`** — Updated `test_build_capabilities_unknown_kind_returns_defaults` to assert `NotImplementedError` instead of silent default (behavior intentionally changed)

**Verification:** 505 tests pass (0 failures, 2 new tests).

---

### Finding #5: `RuntimeFactory.available()` Creates Full Engine Stacks Wastefully

**File:** `factory.py:166-174`

**Code:**
```python
def available(self) -> list[RuntimePreference]:
    available = []
    for kind in RuntimeKind:
        if shutil.which(kind.value):             # already confirms binary exists
            pref = RuntimePreference(kind=kind)
            try:
                self.create(pref)                # creates Transport + 4 managers + parsers
                available.append(pref)
            except RuntimeNotAvailableError:
                continue
    return available
```

**Problem:** `self.create(pref)` builds a complete runtime stack (Transport, all 4 managers, all parsers) for each runtime kind that has a binary — just to call `is_available()` (which runs `--version`). The `shutil.which(kind.value)` check on line 168 already confirmed the binary exists. Creating the full stack is 100x more work than needed.

**Impact:** On every call to `.available()`, the system instantiates and discards a full DI graph per runtime kind. For two runtimes (Docker + Podman), this is wasteful but tolerable. For 4+ runtimes, it compounds.

---

### Proposed Solution

#### Approach: Full Hexagonal Discovery Separation — New `RuntimeDiscovery` Port + Adapter + Transport `probe()` Method

Instead of a lightweight in-factory fix, we extract discovery into its own hexagonal layer. This means three architectural changes work together:

**1. `Transport.probe()` (ports/transport.py)** — Add an abstract `probe() -> bool` method to the `Transport` ABC. This is the protocol-level question "is this binary available and functional?" The answer is `True`/`False`. No `--version`, no `returncode` — those are adapter implementation details. Every transport must implement `probe()`.

**2. `RuntimeDiscovery` port + `CliRuntimeDiscovery` adapter (NEW)** — A new port/adapter pair. `RuntimeDiscovery.available()` iterates `RuntimeKind`, creates a transport for each via `transport_factory`, and calls `transport.probe()`. Only runtimes where `probe()` returns `True` are included. All I/O goes through the Transport port — `CliRuntimeDiscovery` has zero protocol knowledge.

**3. `RuntimeFactory` refactored** — The factory gains a `discovery` property that returns `RuntimeDiscovery` (wired via `RuntimeFactoryConfig.discovery_factory`). `available()` becomes `self.discovery.available()`. The factory knows NOTHING about `--version`, `returncode`, or subprocess. Protocol details are sealed in `CliTransport`.

**Rationale:** This is the cleanest separation of concerns:
- `RuntimeFactory` = assembly (DI graph construction)
- `CliRuntimeDiscovery` = discovery (probe via transport)
- `CliTransport.probe()` = I/O (subprocess, --version, returncode)
- No layer knows protocol details from another layer
- Every layer is independently testable through port injection
- Adding a new runtime requires only a `RuntimeKind` enum member (domain) + transport handles it generically

**Create** `ports/discovery.py`:
```python
from abc import ABC, abstractmethod

from oci_runtime.ports.capabilities import RuntimePreference


class RuntimeDiscovery(ABC):
    """Discovers which container engines are available on this system.

    Separated from RuntimeFactory so the DI root does only assembly.
    Discovery is a query concern — not an assembly concern.
    """

    @abstractmethod
    def available(self) -> list[RuntimePreference]:
        """Return all engines currently available on this system.

        Returns RuntimePreference objects the caller can pass to
        RuntimeFactory.create() to get a working ContainerEngine.
        """
```

**Create** `adapters/discovery/__init__.py`:
```python
# Discovery adapter implementations
```

**Create** `adapters/discovery/cli.py`:
```python
from typing import Callable

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimePreference
from oci_runtime.ports.discovery import RuntimeDiscovery
from oci_runtime.ports.transport import Transport


class CliRuntimeDiscovery(RuntimeDiscovery):
    """Discovers available container engines via CLI probing.

    All I/O happens through the Transport port abstraction.
    No subprocess, no shutil, no protocol details — those belong
    to the Transport adapter.
    """

    def __init__(self, transport_factory: Callable[[str], Transport]):
        self._transport_factory = transport_factory

    def available(self) -> list[RuntimePreference]:
        available = []
        for kind in RuntimeKind:
            pref = RuntimePreference(kind=kind)
            binary = pref.get_binary()
            try:
                transport = self._transport_factory(binary)
                if transport.probe():
                    available.append(pref)
            except Exception:
                continue
        return available
```

**Add to** `ports/transport.py` — new abstract method on `Transport`:
```python
@abstractmethod
def probe(self) -> bool:
    """Whether this transport's binary is available and functional.

    Hexagonal note: This is a port-level operation. The 'how' of probing
    (subprocess, --version, returncode checking) is an adapter concern.
    The caller (factory, discovery) knows nothing about protocol details.
    """
```

**Add to** `adapters/transport/cli.py` — implementation on `CliTransport`:
```python
def probe(self) -> bool:
    try:
        result = subprocess.run(
            [self.binary, "--version"],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
```

**Add to** `tests/integration/conftest.py` — `RecordingTransport` must implement `probe()`:
```python
def probe(self) -> bool:
    return True
```

**Update** `ports/factory.py` — add `discovery_factory` to `RuntimeFactoryConfig`:
```python
@dataclass
class RuntimeFactoryConfig:
    transport_factory: Callable[[str], Transport] | None = None
    runtime_cls: type[ContainerEngine] | None = None
    parser_provider: Callable[[RuntimeKind], Parsers] | None = None
    discovery_factory: Callable[[Callable[[str], Transport]], RuntimeDiscovery] | None = None
```

**Update** `factory.py` — three changes:

1. Add default discovery factory:
```python
def _default_discovery_factory(
    transport_factory: Callable[[str], Transport],
) -> RuntimeDiscovery:
    from oci_runtime.adapters.discovery.cli import CliRuntimeDiscovery
    return CliRuntimeDiscovery(transport_factory)
```

2. Add wiring in `_resolve_config`:
```python
if cfg.discovery_factory is None:
    cfg.discovery_factory = _default_discovery_factory
```

3. Refactor `RuntimeFactory`:
```python
class RuntimeFactory:
    ...
    @property
    def discovery(self) -> RuntimeDiscovery:
        return self._cfg.discovery_factory(self._cfg.transport_factory)

    def available(self) -> list[RuntimePreference]:
        return self.discovery.available()
```

#### Tests to Add/Update

**`tests/unit/adapters/test_discovery.py`** — NEW file, ~15 tests:
- `TestTransportProbeContract` — probe returns bool, handles all states
- `TestCliRuntimeDiscovery` — all runtimes available, mixed, none, transport failure, exploding factory
- `TestRuntimeDiscoveryPort` — ABC cannot be instantiated, contract enforced
- `TestDiscoveryViaFactory` — factory.discovery returns RuntimeDiscovery, factory.available() delegates correctly

**`tests/unit/adapters/test_transport.py`** — 2 new tests:
- `test_probe_returns_true_when_binary_available`
- `test_probe_returns_false_when_binary_not_found`

**`tests/integration/conftest.py`** — Add `probe()` to `RecordingTransport`:
```python
def probe(self) -> bool:
    return True
```

**No changes needed** to existing test files that:
- Call `factory.available()` — backward compatible (same return type, same signature)
- Construct `RuntimeFactoryConfig` — `discovery_factory` defaults to `None`
- Mock `shutil.which` — those mock transport-layer `_ensure_binary`, not factory-level discovery
- Import `Transport` as a type — no runtime impact from adding a new abstract method (unless subclassing)

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|---|---|---|
| Domain: pure Python, no I/O | ✅ Unchanged | `RuntimeKind` enum unchanged. No domain types modified. |
| Ports: ABCs only, no implementation | ✅ | `RuntimeDiscovery` has one `@abstractmethod`. `Transport.probe()` is `@abstractmethod` with docstring only. |
| Ports: No concrete types leaking | ✅ | `RuntimeDiscovery.available()` returns `list[RuntimePreference]` — a port type from `ports/capabilities.py`. |
| Adapters: All I/O lives here | ✅ | `CliTransport.probe()` contains `subprocess.run`, `--version`, `returncode`. `CliRuntimeDiscovery` contains only port-level calls — no I/O. |
| Adapters: Implement port contracts | ✅ | `CliTransport` implements `Transport`. `CliRuntimeDiscovery` implements `RuntimeDiscovery`. |
| Factory: Only DI composition root | ✅ | `RuntimeFactory._cfg` contains all wiring. `discovery_factory` resolved in `_resolve_config`. |
| Factory: Depends on abstractions, not concretions | ✅ | Factory calls `discovery_factory` (returns `RuntimeDiscovery`), not `CliRuntimeDiscovery` directly. `transport_factory` returns `Transport`, not `CliTransport`. |
| Factory: Zero protocol knowledge | ✅ | Factory code contains NO references to `--version`, `returncode`, `subprocess`, `shutil.which`, `stdout`, `stderr`, or `FileNotFoundError`. |
| Separation: Factory ≠ Discovery | ✅ | `RuntimeFactory` does assembly. `CliRuntimeDiscovery` does discovery. Two classes, two responsibilities, one port abstraction between them. |
| Testability: Every layer injectable | ✅ | `MockTransport` (probe control), `MockTransportFactory` (binary-level control), `MockDiscovery` (result control), `Callable` injection in `RuntimeFactoryConfig`. |
| Adding new runtime (OCP) | ✅ | New `RuntimeKind` member auto-discovered. `CliRuntimeDiscovery` iterates `RuntimeKind` — no code change. Only domain enum + capability registry update needed. |

#### Ripple Effect (External)

| Category | Count | Impact |
|---|---|---|
| External consumers of `oci_runtime` | **0** | Module is fully isolated — no other module imports from it |
| `Transport` subclasses that must implement `probe()` | **2** | `CliTransport` (production) + `RecordingTransport` (test double in `conftest.py`) |
| Files constructing `RuntimeFactoryConfig` | **3** | `discovery_factory` defaults to `None` — backward compatible |
| Files calling `.available()` | **2** | Backward compatible — same signature, same return type |
| Files mocking `shutil.which` for transport tests | **12** | Unaffected — those mock `shutil` for `CliTransport._ensure_binary`, not factory discovery |
| **Total production files touched** | **7** | 3 new + 4 modified (all within module) |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-05-30
**Changes applied:**

1. **`ports/transport.py`** — Added `probe() -> bool` abstract method to `Transport` ABC
2. **`ports/discovery.py`** — Created `RuntimeDiscovery` ABC with `available()` abstract method
3. **`adapters/discovery/__init__.py`** — Created empty init for new adapter package
4. **`adapters/discovery/cli.py`** — Created `CliRuntimeDiscovery` implementation with narrowed exception handling `(FileNotFoundError, OSError, RuntimeNotAvailableError)`
5. **`adapters/transport/cli.py`** — Implemented `probe()` on `CliTransport` using `subprocess.run([binary, "--version"], ...)` with `FileNotFoundError`/`TimeoutExpired`/`OSError` handling
6. **`ports/factory.py`** — Added `discovery_factory` field to `RuntimeFactoryConfig`
7. **`factory.py`** — Added `_default_discovery_factory` with lazy import, wired `discovery_factory` in `_resolve_config`, added `RuntimeFactory.discovery` property returning `RuntimeDiscovery`, refactored `available()` to delegate to `self.discovery.available()`, removed `import shutil`
8. **`tests/unit/adapters/test_cli_transport.py`** — Added 4 probe tests: success, binary not found, timeout, OSError
9. **`tests/unit/adapters/test_discovery.py`** — Created with 13 tests: port contract (2), `CliRuntimeDiscovery` behavior (8), `DiscoveryViaFactory` integration (3)
10. **`tests/integration/conftest.py`** — Added `probe() -> bool` returning `True` to `RecordingTransport`
11. **`tests/unit/ports/test_transport.py`** — Added `probe()` to `GoodTransport` test subclass
12. **`tests/integration/contract/test_interface_compliance.py`** — Added `"probe"` to expected abstract methods set
13. **`tests/integration/integration/test_factory_wiring.py`** — Updated `test_available_only_returns_available_runtimes` to mock `subprocess.run` instead of `shutil.which`

**Validation:** 521 tests pass (0 failures, 17 new/updated tests). Full suite across unit and integration.

**Solution rationale:** Extracted discovery into its own hexagonal layer — `Transport.probe()` (port), `RuntimeDiscovery` (port), `CliRuntimeDiscovery` (adapter). The factory now delegates to `self.discovery.available()` which creates only a lightweight transport per runtime kind rather than a full engine stack. `shutil` dependency removed from `factory.py`. Exception handling in `CliRuntimeDiscovery` was narrowed from broad `Exception` to specific expected errors per user decision during TDD implementation.

---

### Finding #6: `_resolve_config` Uses `object.__setattr__` Unnecessarily

**File:** `factory.py:93-102`

**Code:**
```python
def _resolve_config(cfg: RuntimeFactoryConfig | None) -> RuntimeFactoryConfig:
    if cfg is None:
        cfg = RuntimeFactoryConfig()
    if cfg.transport_factory is None:
        object.__setattr__(cfg, "transport_factory", _default_transport_factory)
    if cfg.runtime_cls is None:
        object.__setattr__(cfg, "runtime_cls", _default_runtime_cls())
    if cfg.parser_provider is None:
        object.__setattr__(cfg, "parser_provider", _default_parser_provider)
    return cfg
```

**Problem:** `RuntimeFactoryConfig` is a plain `@dataclass` (NOT `frozen=True`). Normal attribute assignment (`cfg.transport_factory = ...`) works perfectly. `object.__setattr__` is unnecessary and confusing.

**Deep Investigation — Full Analysis:**

1. **Git history:** Both `factory.py` and `ports/factory.py` were introduced in the same commit `423ee5a`. `RuntimeFactoryConfig` was NEVER frozen. There is no version where `object.__setattr__` was needed.

2. **The sibling `Parsers` class IS frozen:**
   ```python
   @dataclass(frozen=True)       # <-- frozen!
   class Parsers:
       cp: ContainerParser
       ...
   
   @dataclass                    # <-- NOT frozen
   class RuntimeFactoryConfig:
       ...
   ```
   The author needed `object.__setattr__` for `Parsers` (frozen) and — by muscle memory or consistency — carried the same pattern to `RuntimeFactoryConfig`.

3. **No `__slots__`, no custom `__setattr__`, no metaclass.** The class is a standard Python dataclass with MRO `[RuntimeFactoryConfig, object]`. Normal assignment works.

4. **No test exercises this directly.** Only integration tests through `RuntimeFactory` touch `_resolve_config` indirectly.

5. **Pros of the current approach:** 
   - Visually screams "this is a deliberate post-construction mutation, not initialization" — the `object.__setattr__` form is eye-catching documentation
   - Defensively safe against a future `__setattr__` being added to `RuntimeFactoryConfig` (unlikely but possible)
   - Bypasses any potential `frozen=True` change in the future

6. **Cons:**
   - Confusing to readers who check whether the class is frozen (it isn't)
   - Unconventional — `object.__setattr__` is usually a last resort
   - Suggests the author may have been confused about frozen vs non-frozen dataclasses

**Verdict:** Harmless but confusing. The `object.__setattr__` pattern suggests the author intended `RuntimeFactoryConfig` to be write-once (like the frozen `Parsers` sibling) but never finished making it frozen.

---

### Proposed Solution

#### Approach: Freeze `RuntimeFactoryConfig` — `@dataclass(frozen=True)`

Make `RuntimeFactoryConfig` explicitly frozen, matching its sibling `Parsers`. The `object.__setattr__` calls in `_resolve_config` become the **correct, necessary** pattern for post-construction initialization on a frozen dataclass — not confusing noise.

**Rationale:** The config was always conceptually write-once:
- No code anywhere mutates a `RuntimeFactoryConfig` after `_resolve_config` returns
- All 3 test injection sites pass values via the constructor, never mutate after
- The `Parsers` class (same file, `ports/factory.py:16`) is already `frozen=True` for the same reason
- Freezing enforces the DI composition root contract: build it once, then read from it

**Change** `ports/factory.py:25`:
```python
@dataclass(frozen=True)  # was: @dataclass
class RuntimeFactoryConfig:
```

**No changes** to `factory.py` — `_resolve_config` keeps `object.__setattr__`, which is now the correct pattern for a frozen dataclass builder.

#### Affected Files (Detailed Audit)

| File | Change | Nature |
|------|--------|--------|
| `ports/factory.py:25` | `@dataclass` → `@dataclass(frozen=True)` | 1-word production change |
| `factory.py:125-136` | Unchanged | `object.__setattr__` stays — now correct pattern |
| `tests/integration/contract/test_interface_compliance.py:454-461` | Unchanged | `is_dataclass` still passes; constructor defaults still work |
| `tests/integration/integration/test_factory_wiring.py:89-157` | Unchanged | All 3 injection tests pass via constructor — no mutation |
| `tests/unit/adapters/test_discovery.py:138` | Unchanged | Constructor injection only |

**No test file modifications required.** Zero.

#### Cross-Cutting Concerns Validated (42 prototype tests)

| Concern | Result | Detail |
|---------|--------|--------|
| `is_dataclass()` | ✅ | Still recognized as dataclass |
| Constructor injection | ✅ | All field combinations work |
| `_resolve_config` defaults | ✅ | `object.__setattr__` fills frozen fields correctly |
| User values preserved | ✅ | Explicit fields not overwritten by defaults |
| `astuple()` / `asdict()` | ✅ | Standard dataclass utilities work |
| `dataclasses.replace()` | ✅ | Available on frozen dataclasses only |
| Post-resolution mutation | ✅ | Blocked — `FrozenInstanceError` raised |
| `Parsers` consistency | ✅ | Both dataclasses now frozen together |

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Ports: ABCs only, no implementation | ✅ Unchanged | `RuntimeFactoryConfig` is a pure `@dataclass` — no behavior, no I/O |
| Ports: No concrete types leaking | ✅ | All fields are `Callable` abstractions or port types |
| Factory: only DI root | ✅ Unchanged | `_resolve_config` unchanged; `RuntimeFactory.__init__` unchanged |
| Factory: depends on abstractions | ✅ Unchanged | All `_cfg.*` reads go through port types |
| Factory: no protocol knowledge | ✅ Unchanged | No transport/parser/engine details in config |
| Consistency with `Parsers` | ✅ | Both `@dataclass(frozen=True)` in same file |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-05-30
**Changes applied:**

1. **`ports/factory.py:25`** — Changed `@dataclass` to `@dataclass(frozen=True)` on `RuntimeFactoryConfig`. The `object.__setattr__` calls in `_resolve_config` remain unchanged — they are now the correct pattern for post-construction initialization on a frozen dataclass.

2. **`dev/validation/oci_runtime/finding-6-freeze-runtimefactoryconfig.py`** — Created with 42 prototype tests validating the approach.

**Validation:** 521/521 tests pass (0 failures, 0 new/updated tests — change was entirely internal).

**Solution rationale:** The dataclass was always conceptually write-once — no code mutates a `RuntimeFactoryConfig` after `_resolve_config` returns, and all 3 test injection sites pass values via the constructor. Freezing enforces the DI composition root contract (build once, read from it) and makes `RuntimeFactoryConfig` consistent with its frozen sibling `Parsers` in the same file.

---

### Finding #7: `execute_pty` Is Dead Code with Critical Implementation Bugs

**Files:** `ports/transport.py:26-27` (abstract method), `adapters/transport/cli.py:107-165` (implementation)

**Deep Investigation — Full Analysis:**

**1. Confirmed dead code:**
Zero production callers across the entire repository. Search for `execute_pty` found 13 matches — all are definitions, stubs, or contract tests verifying the method exists. The only "test" that calls it (`test_transport_command.py:67-71`) mocks the internals and only asserts the return type is `ExecResult`.

The `RecordingTransport` in `tests/integration/conftest.py:29-30` returns hardcoded empty results — confirming test authors never needed real PTY logic.

**2. The implementation uses an unusual pattern:**
```python
master_fd, slave_fd = pty.openpty()
pid = os.fork()
if pid == 0:
    os.close(master_fd)
    os.dup2(slave_fd, 0)
    os.dup2(slave_fd, 1)
    os.dup2(slave_fd, 2)
    os.close(slave_fd)
    os.execvp(command[0], command)
    os._exit(1)
```

The `os.fork()` + `os.execvp()` approach is unusual. The sibling `container-manager` module uses `subprocess.Popen(stdin=slave_fd, stdout=slave_fd, stderr=slave_fd)` which is more portable (no `os.fork()` on non-POSIX) and less prone to zombie/reaping bugs.

**3. Critical bugs found in the implementation:**

| # | Bug | Location | Severity |
|---|-----|----------|----------|
| 7a | **`ContainerRuntimeError` not imported** — would cause `NameError` on any exception | `cli.py:165` | 🔴 |
| 7b | **2-second select timeout causes premature exit** — any command idle for >2s gets truncated | `cli.py:139-141` | 🔴 |
| 7c | **No `os.fork()` failure check** — if fork returns `-1`, `waitpid(-1, 0)` reaps wrong child | `cli.py:121` | 🟠 |
| 7d | **`except Exception` catches `KeyboardInterrupt`, `SystemExit`** — Ctrl+C swallowed | `cli.py:159-165` | 🟡 |
| 7e | **Zombie risk** if parent crashes between `os.fork()` and `os.waitpid()` | `cli.py:121-151` | 🔵 |

**4. The TTY connection:**
`CliContainerManager.run()` adds `-t` when `effective_tty` is True but calls `self._transport.execute()` (no PTY) instead of `execute_pty()`. This gives the container a PTY but not the host process. For `docker exec -it container bash` to work correctly, BOTH container-side `-t` AND host-side PTY are needed. The code currently only does the former.

The `RunConfig.effective_tty` property correctly detects when a PTY is needed, but `CliContainerManager.run()` never dispatches to `execute_pty()`.

**5. The previous audit report was wrong:** It claimed `execute_pty` is "unimplemented" at `docs/oci-runtime-audit-report.md:43`. It IS implemented — but the implementation is buggy and disconnected from callers.

**Verdict:** The method was likely added proactively for future TTY support, but it was never wired into the `run()` method, never tested, and contains multiple critical bugs that make it dangerous if ever called.

### Prototype Validation

**Files:** `dev/validation/oci_runtime/finding-7a-pty-utility.py`, `finding-7b-transport-impact.py`, `finding-7c-integration-validation.py`

Three standalone Python scripts were created to validate the approach end-to-end with 58 tests total.

#### Prototype 1: PTY Utility (finding-7a — 19 tests)
Validates the standalone `run_pty()` function using the `subprocess.Popen(stdin=slave_fd, stdout=slave_fd, stderr=slave_fd)` approach, modelled after the sibling `container-manager` module's `run_cli_pty()`.

| Check | Result | Evidence |
|-------|--------|----------|
| Basic command execution | ✅ 19/19 | PTY runs commands, streams output, returns correct exit code |
| Non-zero exit raises error | ✅ Confirmed | `ContainerRuntimeError` raised with exit code in message |
| Missing binary raises `RuntimeNotAvailableError` | ✅ Confirmed | Proper error propagation |
| `effective_tty` dispatch logic | ✅ Confirmed | `tty=True` → PTY path (returns `""`), `tty=False` → non-PTY path (returns captured output) |
| `effective_tty` property logic | ✅ Confirmed | All 5 combinatorial states correct |
| Bug 7a fixed: No missing import | ✅ Confirmed | `ContainerRuntimeError` defined at module level |
| Bug 7b fixed: No 2-second truncation | ✅ Confirmed | `select.timeout=0.1` + `poll()` guard, no break-on-timeout |
| Bug 7c fixed: No `os.fork()` | ✅ Confirmed | Uses `subprocess.Popen` — no `os.fork()`, no `os.waitpid()` |
| Bug 7d fixed: No bare `except Exception` | ✅ Confirmed | Only `except (ValueError, OSError)` |
| Bug 7e fixed: No zombie risk | ✅ Confirmed | `Popen.wait()` reaps automatically |
| Streaming to `sys.stdout.buffer` | ✅ Confirmed | Real-time output, verified with captured fake stdout |
| Post-exit drain loop | ✅ Confirmed | Remaining data drained after process exits |
| Architecture: `Popen` with slave fd | ✅ Confirmed | Uses `stdin=slave_fd`, `stdout=slave_fd`, `stderr=slave_fd` |

#### Prototype 2: Transport ABC Impact (finding-7b — 16 tests)
Validates that removing `execute_pty` from the `Transport` ABC is safe and all test doubles still function.

| Check | Result | Evidence |
|-------|--------|----------|
| `Transport` is still ABC | ✅ 16/16 | All abstract method contracts hold |
| `execute_pty` NOT in ABC | ✅ Confirmed | `hasattr(Transport, "execute_pty")` is `False` |
| Only 3 abstract methods remain | ✅ Confirmed | `{"execute", "get_runtime_binary", "probe"}` |
| Cannot instantiate Transport | ✅ Confirmed | `TypeError` raised as expected |
| `GoodTransport` works without `execute_pty` | ✅ Confirmed | Minimal implementation validates |
| `RecordingTransport` works | ✅ Confirmed | Integration test double functional |
| `_make_transport()` helper works | ✅ Confirmed | Test helper pattern validated |
| No production code calls `execute_pty` | ✅ Confirmed | Zero callers identified |
| No factory changes needed | ✅ Confirmed | `Transport` ABC is the only touch point |

#### Prototype 3: Integration Validation (finding-7c — 23 tests)
Validates the full end-to-end flow from `RunConfig` → dispatch → PTY/non-PTY execution.

| Check | Result | Evidence |
|-------|--------|----------|
| PTY basic execution | ✅ 23/23 | `run_pty` with `/bin/sh -c` succeeds, streams to stdout |
| Non-zero exit raises | ✅ Confirmed | `ContainerRuntimeError` with correct exit code |
| Empty command raises | ✅ Confirmed | Proper error for empty cmd |
| PTY dispatch (no transport call) | ✅ Confirmed | PTY path bypasses `transport.execute()` |
| Non-PTY dispatch (captured output) | ✅ Confirmed | `RecordingTransport` returns `"abc123"` |
| Stream mode returns `""` | ✅ Confirmed | `stream_output=True` returns empty |
| `detach` + `tty` raises error | ✅ Confirmed | Mutual exclusion enforced |
| `effective_tty` all states | ✅ Confirmed | All combinatorial states correct |
| PTY return value contract | ✅ Confirmed | Returns `CompletedProcess` with `stdout=b""` |
| Non-PTY return value contract | ✅ Confirmed | Returns captured `str` from `ExecResult.stdout` |
| Transport contract without `execute_pty` | ✅ Confirmed | All doubles implement only required methods |
| Bug-7a through 7e all fixed | ✅ Confirmed | Source inspection validates all 5 bugs eliminated |
| Real PTY output streaming | ✅ Confirmed | `sys.stdout.buffer` receives output in real time |
| Multi-line output preserved | ✅ Confirmed | Both lines present in drained output |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-05-30
**Changes applied:**

1. **`ports/transport.py`** — Removed `execute_pty` abstract method from `Transport` ABC. Transport now has 3 clean abstract methods: `execute()`, `get_runtime_binary()`, `probe()`.
2. **`adapters/transport/cli.py`** — Removed buggy `execute_pty` implementation (lines 107–165) — 59 lines eliminated. Eliminated all 5 bugs (7a–7e): `ContainerRuntimeError` import missing, 2-second select timeout, `os.fork()` crash risk, bare `except Exception`, zombie risk.
3. **`adapters/managers/pty.py`** — Created standalone PTY utility module with `run_pty()` function using portable `subprocess.Popen(stdin=slave_fd, ...)` pattern (matching sibling container-manager module) instead of `os.fork()`/`os.execvp()`.
4. **`adapters/managers/container.py`** — Wired PTY dispatch in `CliContainerManager.run()`: uses `effective_tty` property, detach+TTY mutual exclusion, routes to `run_pty()` when PTY needed, returns `""` for stream/PTY paths.
5. **`tests/unit/ports/test_transport.py`** — Removed `test_execute_pty_is_abstract`, removed `execute_pty` from `GoodTransport`
6. **`tests/unit/ports/test_managers.py`** — Removed `execute_pty` from `_make_transport()`, added `probe()` method
7. **`tests/integration/conftest.py`** — Removed `execute_pty` from `RecordingTransport`
8. **`tests/integration/contract/test_interface_compliance.py`** — Updated expected abstract methods to `{"execute", "get_runtime_binary", "probe"}`; swapped `assert callable(t.execute_pty)` → `assert callable(t.probe)` in 2 tests
9. **`tests/integration/integration/test_transport_command.py`** — Removed `test_execute_pty_is_implemented`
10. **`tests/unit/adapters/test_cli_pty.py`** — **NEW:** 10 unit tests for `run_pty()` covering empty command, missing binary, basic execution, non-zero exit, streaming output, drain after exit, non-UTF-8, large output, select errors, Popen failure
11. **`tests/integration/container/test_tty_dispatch.py`** — **NEW:** 10 integration tests for PTY dispatch covering TTY/non-TTY paths, detach+TTY mutual exclusion, auto_tty detection, return contracts, default flags passthrough
12. **`tests/integration/functional/test_workflows.py`** — Updated `test_container_run_with_all_options` to use `tty=False` (detach+TTY now mutually exclusive per plan)
13. **`tests/integration/integration/test_manager_commands.py`** — Updated `test_run_with_all_options` to use `tty=False` (same reason)

**Verification:** 539 tests pass (0 failures) across unit and integration suites. 20 new tests added (10 PTY utility + 10 TTY dispatch).

**Solution rationale:** Removed `execute_pty` from the Transport ABC (ports layer) and relocated PTY capability to a manager-level adapter utility (`adapters/managers/pty.py`). PTY is not a transport concern — transports execute commands and return `ExecResult`. The new `run_pty()` function uses the same `subprocess.Popen(stdin=slave_fd)` approach proven by the sibling container-manager module, eliminating all 5 critical bugs in the old implementation. `CliContainerManager.run()` dispatches to PTY vs non-PTY paths based on `RunConfig.effective_tty`, including mutual exclusion enforcement for `detach=True` + TTY.

---

### Finding #20: Factory Has Import-Time Side Effects via Module-Level `register_provider()`

**File:** `factory.py:47-51`

**Code:**
```python
from oci_runtime.adapters.provider.docker import DockerRuntimeProvider
from oci_runtime.adapters.provider.podman import PodmanRuntimeProvider

register_provider(DockerRuntimeProvider())
register_provider(PodmanRuntimeProvider())
```

**Problem:** Simply importing `oci_runtime` or `oci_runtime.factory` **creates instances of Docker and Podman providers** and registers them in a global module-level registry. This is an import-time side effect that:
1. Prevents lazy initialization — providers are constructed even if the user only wants Podman.
2. Makes the module stateful at import time — any code that patches `register_provider` or modifies `_PROVIDER_REGISTRY` must account for this already having run.
3. Breaks test isolation — the global registry persists across test cases unless explicitly cleaned up.
4. Contradicts the factory's own docstring: *"Depends on abstractions (ports), not implementations (adapters)"* — but the module-level code eagerly imports 2 adapter implementations.

**Root cause:** The `RuntimeProvider` pattern (Finding #10) solved the OCP violation but introduced eager registration as a side effect. The registrations should be lazy or triggered by explicit configuration.

**Contrast with `_resolve_config`:** The factory's other defaults (`_default_transport_factory`, `_default_discovery_factory`, etc.) are lazy — they are only constructed when `RuntimeFactoryConfig` fields are `None`. Provider registration is the only eager initialization.

**Fix:** Move the `register_provider()` calls into `RuntimeFactory.__init__()` or into a public `oci_runtime.configure()` function that users call explicitly. Alternatively, make provider registration lazy in `_resolve_config`:
```python
def _resolve_config(cfg):
    ...
    if not _PROVIDER_REGISTRY:
        register_provider(DockerRuntimeProvider())
        register_provider(PodmanRuntimeProvider())
    ...
```

### Proposed Solution

#### Approach: Lazy registration in `_resolve_config()` — function-local imports gated by empty registry check

Move the `register_provider()` calls and their adapter imports from module-level (import-time) into `_resolve_config()`, gated by `if not _PROVIDER_REGISTRY`. This mirrors the existing lazy pattern used by `_default_transport_factory`, `_default_discovery_factory`, and every other default in the same file — they are all function-local imports inside `_resolve_config()`.

The global `_PROVIDER_REGISTRY` dict stays at module level (it's inert data, not a side effect). Only the `register_provider()` calls that populate it move.

**Remove** from `factory.py:47-51` (module-level):
```python
from oci_runtime.adapters.provider.docker import DockerRuntimeProvider
from oci_runtime.adapters.provider.podman import PodmanRuntimeProvider

register_provider(DockerRuntimeProvider())
register_provider(PodmanRuntimeProvider())
```

**Add** inside `_resolve_config()`, before the `if cfg.* is None` blocks:
```python
def _resolve_config(cfg: RuntimeFactoryConfig | None) -> RuntimeFactoryConfig:
    if cfg is None:
        cfg = RuntimeFactoryConfig()

    if not _PROVIDER_REGISTRY:
        from oci_runtime.adapters.provider.docker import DockerRuntimeProvider
        from oci_runtime.adapters.provider.podman import PodmanRuntimeProvider

        register_provider(DockerRuntimeProvider())
        register_provider(PodmanRuntimeProvider())

    if cfg.transport_factory is None:
        ...
```

**Also update** `factory.py` — the `Remove` block above covers the 4 lines (2 imports + 2 register_provider calls). After removal, importing `factory.py` triggers no adapter imports at the module level. The remaining 5 adapter imports (`CliRuntime`, `CliContainerManager`, `CliImageManager`, `CliNetworkManager`, `CliVolumeManager`) should also be moved into their respective `_default_runtime_cls()` and `_make_*_manager()` functions to make the lazy pattern consistent — all adapter imports function-local, none at module level.

#### What Changes

| Scenario | Before | After |
|----------|--------|-------|
| `import oci_runtime` | Docker + Podman providers constructed and registered | No side effects — module loads cleanly |
| First `RuntimeFactory()` | Providers already registered at import time | `_resolve_config()` finds empty registry → registers providers lazily |
| Second `RuntimeFactory()` | Providers already registered (no-op missed) | `if not _PROVIDER_REGISTRY` is `False` → no-op |
| Test isolation | Global registry persists across test cases | `_PROVIDER_REGISTRY.clear()` between tests gives clean state |
| Custom provider registration | Must account for already-registered builtins | Clean slate — user registers first, `_resolve_config` skips if non-empty |

#### Tests to Add/Update

**3 files affected: 1 production + 2 test files.**

**`factory.py`** — Remove 4 module-level lines (lines 47-51). Add 7 lines inside `_resolve_config()`. See code snippets above. Additionally move the 5 remaining module-level adapter imports into their respective builder functions.

**`tests/unit/adapters/test_providers.py` — REQUIRED CHANGE.** `TestProviderRegistry` (lines 168-207) calls `get_provider(RuntimeKind.DOCKER)` on line 170, which currently works because the module-level `register_provider()` ran at import time. After the fix, no providers are registered at import time — the test gets `NotImplementedError`. Fix: add `setup_method` to explicitly register providers and `teardown_method` to clean up:

```python
class TestProviderRegistry:
    def setup_method(self):
        from oci_runtime.factory import _PROVIDER_REGISTRY
        _PROVIDER_REGISTRY.clear()
        from oci_runtime.factory import register_provider
        from oci_runtime.adapters.provider.docker import DockerRuntimeProvider
        from oci_runtime.adapters.provider.podman import PodmanRuntimeProvider
        register_provider(DockerRuntimeProvider())
        register_provider(PodmanRuntimeProvider())

    def teardown_method(self):
        from oci_runtime.factory import _PROVIDER_REGISTRY
        _PROVIDER_REGISTRY.clear()

    def test_get_provider_docker(self):        # unchanged
        provider = get_provider(RuntimeKind.DOCKER)
        assert isinstance(provider, DockerRuntimeProvider)
        assert provider.kind == RuntimeKind.DOCKER

    def test_get_provider_podman(self):        # unchanged
        provider = get_provider(RuntimeKind.PODMAN)
        assert isinstance(provider, PodmanRuntimeProvider)
        assert provider.kind == RuntimeKind.PODMAN

    def test_get_provider_unknown_kind_raises(self):    # unchanged
        ...

    def test_register_provider_duplicate_raises(self):  # unchanged
        ...

    def test_get_provider_returns_provider_with_correct_kind(self):  # unchanged
        for kind in [RuntimeKind.DOCKER, RuntimeKind.PODMAN]:
            provider = get_provider(kind)
            assert provider.kind == kind
```

The 5 test method bodies are unchanged. Only `setup_method` and `teardown_method` are new.

**Why no autouse conftest fixture for test isolation:** An autouse fixture that clears `_PROVIDER_REGISTRY` before every test would break every other test that uses `get_provider()` without explicitly registering (including `TestProviderRegistry` itself, and any future test that assumes providers exist). The targeted `setup_method`/`teardown_method` approach makes `TestProviderRegistry` self-contained without poisoning other test scopes.

**`tests/unit/adapters/test_factory.py` — REQUIRED new test.** The subprocess-based isolation test is mandatory, not optional. No in-process test can validate import-time behavior — by the time `import oci_runtime.factory` returns in a standard test, any side effects have already executed. A subprocess gives a clean interpreter where we can inspect `_PROVIDER_REGISTRY` before any `RuntimeFactory()` is created. The test validates both directions (import purity + lazy registration) in a single subprocess to minimize overhead:

```python
def test_importing_factory_has_no_side_effects():
    import os
    import subprocess
    import sys

    code = """\
from oci_runtime.factory import _PROVIDER_REGISTRY, RuntimeFactory

# 1. Import must NOT trigger side effects
assert len(_PROVIDER_REGISTRY) == 0, \
    f"Import triggered side effects: {list(_PROVIDER_REGISTRY.keys())}"

# 2. Lazy registration must happen on first factory creation
factory = RuntimeFactory()
assert len(_PROVIDER_REGISTRY) == 2, \
    f"Expected 2 providers, got {len(_PROVIDER_REGISTRY)}: {list(_PROVIDER_REGISTRY.keys())}"
"""

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": ":".join(sys.path)},
    )
    assert result.returncode == 0, result.stderr
```

A subprocess is the only reliable way to test import-time behavior — `importlib.reload()` does not fully reset cached sub-modules, and by the time an in-process import statement completes, any side effects have already executed. The `PYTHONPATH` passthrough ensures the subprocess can discover `oci_runtime` the same way the parent interpreter does. The ~100ms one-time cost is negligible in a 600+ test suite.

If a future refactoring moves `register_provider()` back to module level, this test fails — the only regression test for the core fix.

**Other test files are unaffected:**
- `test_factory.py` (existing tests) — `RuntimeFactory()` → `_resolve_config()` → lazy registration. Works identically.
- `test_factory_wiring.py` — same pattern. Works.
- `test_discovery.py` — same pattern. Works.
- `test_providers.py:TestDockerRuntimeProvider`, `TestPodmanRuntimeProvider`, parser type tests — create provider instances directly via constructor. No dependency on module-level registration.

#### Files Affected Summary

| File | Change | Lines |
|------|--------|-------|
| `factory.py` | Remove 4 module-level lines, add 7 lines inside `_resolve_config()`; move 5 adapter imports to function-local | -9/+12 production |
| `tests/unit/adapters/test_providers.py` | Add `setup_method` + `teardown_method` to `TestProviderRegistry` | +12 test |
| `tests/unit/adapters/test_factory.py` | Add `test_importing_factory_has_no_side_effects` | +16 test |
| **Total** | **3 files** | **-9/+28 = +19 net lines** |

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|---|---|---|
| Domain: pure Python, no I/O | ✅ Unchanged | No domain types touched |
| Ports: ABCs only, no implementation | ✅ Unchanged | `RuntimeProvider` port (`ports/provider.py`) unchanged |
| Ports: no adapter imports | ✅ Unchanged | Port has no adapter dependencies |
| Adapters: implement contracts, contain I/O | ✅ | Provider classes unchanged; only their instantiation moves to a lazy code path |
| Adapters: imports inside function (lazy) | ✅ Improved | Every adapter import is now function-local — not at module level |
| Factory: only DI composition root | ✅ Unchanged | `RuntimeFactory.create()` still calls `get_provider()` — identical behavior |
| Factory: depends on abstractions, not concretions | ✅ Improved | Factory module top-level imports only ports, domain types, and stdlib |
| Factory: zero protocol knowledge | ✅ Unchanged | `get_provider()` returns `RuntimeProvider` ABC — no adapter details leak |
| Test isolation | ✅ Improved | `TestProviderRegistry.setup_method`/`teardown_method` provides clean state per test class |

The fix makes the factory's initialization fully consistent — every default is lazy, all adapter imports are function-local.

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-06-03
**Changes applied:**

1. **`factory.py`** — Removed 4 module-level lines (2 provider imports + 2 `register_provider()` calls). Added lazy registration inside `_resolve_config()` with `if not _PROVIDER_REGISTRY` guard, using function-local adapter imports. Also moved 5 remaining module-level adapter imports (`CliRuntime`, `CliContainerManager`, `CliImageManager`, `CliNetworkManager`, `CliVolumeManager`) into their respective `_default_runtime_cls()` and `_make_*_manager()` functions — all adapter imports are now lazy.
2. **`tests/unit/adapters/test_providers.py`** — Added `setup_method` and `teardown_method` to `TestProviderRegistry` for self-contained test isolation (clears and re-registers providers per test class).
3. **`tests/unit/adapters/test_factory.py`** — Added `test_importing_factory_has_no_side_effects` subprocess test validating that import does not trigger provider registration and that lazy registration happens on first `RuntimeFactory()` creation.

**Solution rationale:** Moved `register_provider()` calls and all adapter imports from module-level into function-local lazy imports inside `_resolve_config()` and the `_make_*` builder functions. The module-level `_PROVIDER_REGISTRY` dict is inert data (no side effect). Importing `oci_runtime` or `oci_runtime.factory` now triggers zero adapter module loads and zero instance creation — providers are registered only when `_resolve_config()` runs on the first `RuntimeFactory()` construction. The 5 remaining manager/engine adapter imports were also moved to follow the same lazy pattern, making the factory consistent: every adapter import is function-local.

**Verification:** 641 tests pass (0 failures) across unit and integration suites.

---

## 🟡 MEDIUM-SEVERITY / ARCHITECTURAL DRIFT

### Finding #8: `ContainerState` Enum Is Dead Code (3 States vs 7 Engine States)

**File:** `domain/enums.py:9-12`

**Code:**
```python
class ContainerState(Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
```

**Defined but never imported or used anywhere** in the module. `ContainerInfo.state` is typed as `str` instead. The test `test_enums.py:42-51` explicitly asserts this is a closed, OCI-spec-only set:

```python
def test_closed_set_oci_states_only(self):
    members = set(ContainerState.__members__)
    assert members == {"CREATED", "RUNNING", "STOPPED"}
```

**Deep Investigation — Container State Analysis:**

**Docker and Podman actual states (7 values):**
| State | Docker `State.Status` | Podman `State.Status` |
|-------|----------------------|----------------------|
| `created` | ✅ | ✅ |
| `running` | ✅ | ✅ |
| `paused` | ✅ | ✅ |
| `restarting` | ✅ | ✅ |
| `removing` | ✅ | ✅ |
| `exited` | ✅ | ✅ (Docker's "stopped") |
| `dead` | ✅ | ✅ |

**OCI Runtime Specification states (4 values):**
- `creating` (transitional, not seen in inspect output)
- `created`
- `running`
- `stopped` (OCI term = Docker/Podman's `exited`)

The OCI spec explicitly states: *"Additional values MAY be defined by the runtime."* So `paused`, `restarting`, `removing`, `dead` are valid runtime-specific extensions.

**There are TWO `ContainerState` enums in the codebase:**
- `oci_runtime/domain/enums.py` — 3 values (OCI subset)
- `container_manager/core/enums.py` — 7 values (engine-complete)

Neither is used as the type annotation for `ContainerInfo.state` — both modules type it as `str`.

**Verdict:** The 3-value enum is deliberately OCI-spec-only but is too narrow for production use. It should either be expanded to 7 values to match engine reality, or removed in favor of `str` with a comment explaining the valid values.

---

### Proposed Solution (Combined Fix for Finding #8 + #12)

#### Approach: `ContainerState` as `StrEnum` + `ContainerInfo.state: ContainerState`

Replace the 3-value `ContainerState(Enum)` with a 7-value `ContainerState(StrEnum)` that matches engine-complete reality. `StrEnum` inherits from `str`, so every member IS a string — `ContainerState.RUNNING == "running"` is `True`, enabling drop-in backward compatibility with all existing code that compares `info.state == "running"`.

`ContainerInfo.state` is re-typed from `str` to `ContainerState`, giving callers named constants and enabling `match/case` pattern matching.

**Parser integration** is a one-liner: wrap the engine state string in `ContainerState(value)`. The default `StrEnum` constructor raises `ValueError` for unknown values — this is intentional. If a future runtime returns an unknown state, it crashes loud at the adapter boundary, enforcing that every new engine state must be explicitly added to the domain enum. This is architecturally correct: the domain models the closed set of known states; the adapter does not silently swallow unknown data.

**Update** `domain/enums.py`:
```python
from enum import StrEnum


class ContainerState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    REMOVING = "removing"
    EXITED = "exited"
    DEAD = "dead"
```

**Update** `domain/types.py` — Change `ContainerInfo.state` type:
```python
state: ContainerState
```

**Update** `adapters/parser/docker.py` (2 sites) — Wrap engine strings in `ContainerState`:
- `parse_inspect` line 34: `state=ContainerState(item.get("State", {}).get("Status", ContainerState.CREATED))`
- `parse_list` line 55: `state=ContainerState(item.get("State", ContainerState.CREATED))`

**Update** `adapters/parser/podman.py` (2 sites) — Same pattern:
- `parse_inspect` line 68: `state=ContainerState(item.get("State", {}).get("Status", ContainerState.CREATED))`
- `parse_list` line 89: `state=ContainerState(item.get("State", ContainerState.CREATED))`

#### Tests to Update

**`tests/unit/domain/test_enums.py`** — Update `TestContainerState`:
- Change `test_closed_set_oci_states_only` to assert 7 members instead of 3
- Remove `test_no_docker_specific_states` (the negative tests for PAUSED, RESTARTING, REMOVING, EXITED, DEAD) — these are now valid members
- Add `test_unknown_state_raises_value_error` — confirms `ContainerState("unknown")` raises `ValueError`
- Add `test_empty_string_raises_value_error` — confirms `ContainerState("")` raises `ValueError`
- Add tests confirming `StrEnum` behavior: `isinstance(x, str)`, `"running" == ContainerState.RUNNING`, f-strings, JSON serialization

**No changes needed** to `test_types.py` — existing tests use `state="running"` and `state="exited"` which work identically with `StrEnum` (the enum members ARE strings).

**No changes needed** to parser tests — parsers produce `ContainerInfo` with `ContainerState`; comparisons like `assert info.state == "running"` continue to work.

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|---|---|---|
| Domain: pure Python, no I/O | ✅ Unchanged | `StrEnum` uses only `enum.StrEnum` — stdlib only, no adapter imports |
| Domain: no transport types | ✅ Unchanged | No `bytes`, `ExecResult`, or subprocess types leak into domain |
| Ports: ABCs only, no implementation | ✅ Unchanged | Port contracts (`ContainerParser`, etc.) unchanged — still return `ContainerInfo` |
| Adapters: implement contracts, map at boundary | ✅ | Parsers wrap engine state strings in `ContainerState(value)` — one-liner at the adapter boundary |
| Adapters: contain all I/O | ✅ Unchanged | Parser `json.loads()` stays in adapter layer |
| Adapters: crash loud on unknown data | ✅ | Unknown engine state raises `ValueError` at adapter boundary — no silent fallback |
| Factory: only DI composition root | ✅ Unchanged | No factory changes needed |
| Future-runtime enforcement | ✅ | New engine state must be explicitly added to domain enum — implementation forced at compile/test time |
| Backward compatible | ✅ | `StrEnum` IS `str` — all `info.state == "running"` comparisons continue to work |
| Sibling module alignment | ✅ | Matches `container_manager.core.enums.ContainerState` (same 7 values) |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-05-31
**Changes applied:**

1. **`domain/enums.py`** — Changed `ContainerState` from 3-value `Enum` to 7-value `StrEnum` (`CREATED`, `RUNNING`, `PAUSED`, `RESTARTING`, `REMOVING`, `EXITED`, `DEAD`). Added `StrEnum` import.
2. **`domain/types.py`** — Changed `ContainerInfo.state` type from `str` to `ContainerState`. Added `ContainerState` import.
3. **`adapters/parser/docker.py`** — Wrapped 2 parser sites in `ContainerState(value)`: `parse_inspect` (line 34) and `parse_list` (line 55), with `ContainerState.CREATED` as default fallback.
4. **`adapters/parser/podman.py`** — Same pattern: wrapped 2 parser sites in `ContainerState(value)`, same default fallback.
5. **`tests/unit/domain/test_enums.py`** — Replaced 3-OCI-state tests with 7-engine-state tests: `test_is_strenum`, `test_has_*` (7 members), `test_closed_set_engine_states`, `test_unknown_state_raises_value_error`, `test_empty_string_raises_value_error`, `test_strenum_is_str`, `test_strenum_equality_with_str`, `test_strenum_not_equal_to_wrong_str`, `test_strenum_fstring`.
6. **`tests/unit/domain/test_types.py`** — Added `test_state_is_typed_as_container_state` confirming `ContainerInfo.state` field type is `ContainerState`.

**Solution rationale:** Changed `ContainerState` from 3-value `Enum` to 7-value `StrEnum`, enabling `ContainerInfo.state` to be properly typed as `ContainerState` instead of `str`. `StrEnum` members ARE strings, so all existing `info.state == "running"` comparisons continue to work. Unknown engine states raise `ValueError` at the adapter boundary, enforcing that new engine states must be explicitly added to the domain enum.

**Verification:** 560/560 tests pass (0 failures).

---

### Finding #9: Domain Types Missing from Public API

**File:** `__init__.py`

**Code:**
```python
__all__ = ["RuntimeFactory", "RuntimePreference", "engines"]
```

**Problem:** Core domain types (`RunConfig`, `BuildContext`, `ContainerInfo`, `ImageInfo`, `VolumeMount`, `PortMapping`, etc.) are not exported from the top-level package. Consumers must know the deep import path `oci_runtime.domain.types.RunConfig`. This harms discoverability and suggests the module's public surface is incomplete.

### Proposed Solution

#### Approach: Expand `__all__` to include all domain types

Add imports and exports for every public domain type in `__init__.py`. This makes all types available from `from oci_runtime import RunConfig` instead of requiring `from oci_runtime.domain.types import RunConfig`.

**Update** `__init__.py`:
```python
from oci_runtime.domain.enums import ContainerState
from oci_runtime.domain.types import (
    BuildContext,
    ContainerInfo,
    ImageInfo,
    NetworkInfo,
    PortMapping,
    RunConfig,
    VolumeInfo,
    VolumeMount,
)

__all__ = [
    "BuildContext",
    "ContainerInfo",
    "ContainerState",
    "engines",
    "ImageInfo",
    "NetworkInfo",
    "PortMapping",
    "RunConfig",
    "RuntimeFactory",
    "RuntimePreference",
    "VolumeInfo",
    "VolumeMount",
]
```

#### Tests to Add/Update

No test changes needed — existing tests import from deep paths (`oci_runtime.domain.types.RunConfig`) which still work. This is purely additive.

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|---|---|---|
| Domain: pure Python, no I/O | ✅ Unchanged | `__init__.py` re-exports domain types — no business logic |
| Ports: ABCs only, no implementation | ✅ Unchanged | Port ABCs not modified |
| Adapters: implement contracts, contain I/O | ✅ Unchanged | No adapter code modified |
| Factory: only DI composition root | ✅ Unchanged | Factory imports unchanged |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-05-31
**Changes applied:**

1. **`__init__.py`** — Expanded `__all__` from 3 exports (`RuntimeFactory`, `RuntimePreference`, `engines`) to 12 exports, adding `BuildContext`, `ContainerInfo`, `ContainerState`, `ImageInfo`, `NetworkInfo`, `PortMapping`, `RunConfig`, `VolumeInfo`, `VolumeMount`. Added corresponding imports from `oci_runtime.domain.enums` and `oci_runtime.domain.types`.

**Solution rationale:** Made all public domain types importable from the top-level package surface, improving discoverability without breaking existing deep-import consumers.

**Verification:** 560/560 tests pass (0 failures).

---

### Finding #10: Factory Violates Open-Closed Principle (OCP) — No Plugin Mechanism

**Files:** `factory.py:27-87`, `domain/enums.py:4-6`, `engines.py:4-8`

**Context: what Finding #4 already fixed**

Finding #4 (resolved) replaced the original hardcoded `if`-chains in `build_capabilities()` and `build_parsers()` with registry dicts:
```python
# Original (Finding #4 — DONE):
_CAPABILITY_REGISTRY = {
    RuntimeKind.DOCKER: RuntimeCapabilities(...),
    RuntimeKind.PODMAN: RuntimeCapabilities(...),
}
_PARSER_REGISTRY = {
    RuntimeKind.DOCKER: _load_docker_parsers,
    RuntimeKind.PODMAN: _load_podman_parsers,
}
```
This eliminated the silent-fallback danger and made the dispatch table-driven instead of branch-driven. **However, adding a new runtime still requires editing `factory.py`** — adding entries to both registries plus a parser loader function. The factory remains the bottleneck: every runtime's capabilities and parsers are defined in two separate places that must be kept in sync.

**What remains: the OCP violation**

Even with registry dicts, the **knowledge of what capabilities and parsers belong to which runtime is scattered across the factory file**, not encapsulated in a single unit. The `RuntimeKind` enum, `engines.py` profiles, capability dict, parser dict, and parser loaders are all separate artifacts that must be changed together. There is no one place that says "this is what Docker is" or "this is what Podman is."

Adding nerdctl today requires editing **17 files** with **89 `RuntimeKind` references** — down from the original if-chain approach, but still fragile and error-prone.

**Deep Investigation — OCP Analysis:**

1. **Two registries that must stay in sync.** `_CAPABILITY_REGISTRY` and `_PARSER_REGISTRY` always change together for a given runtime, but there's no contract enforcing this. Adding nerdctl means editing 3 separate constructs in factory.py (capability entry, parser loader function, parser registry entry).

2. **No encapsulation of runtime identity.** A runtime's kind string, capabilities, and parsers are conceptually one unit — they describe a single engine. But they live in separate data structures across the file.

3. **The OCI ecosystem IS an open set.** Realistically addable runtimes beyond Docker/Podman include:
   - **nerdctl** — containerd's Docker-compatible CLI (high priority)
   - **Finch** — Amazon's nerdctl-based runtime
   - **containerd (ctr)** — lower-level, different CLI design

4. **The `available()` method auto-discovers new `RuntimeKind` enum members** (`for kind in RuntimeKind`), but there's no automatic mechanism to provide capabilities and parsers for them — the gap is a `NotImplementedError` instead of a silent fallback (thanks to Finding #4).

5. **Estimated touch points for adding nerdctl:** 17 files, 89 `RuntimeKind` references.

**Verdict:** The registry dicts from Finding #4 eliminated the silent-fallback danger and made dispatch table-driven. The next step is to encapsulate all runtime-specific knowledge (kind, capabilities, parsers) into a single abstraction — a **RuntimeProvider port** — so that adding a new runtime requires zero changes to factory.py.

### Proposed Solution

#### Approach: `RuntimeProvider` Port — encapsulate all runtime-specific knowledge in a single adapter class

Replace the two separate registries (`_CAPABILITY_REGISTRY` + `_PARSER_REGISTRY`) in `factory.py` with a single `RuntimeProvider` ABC (port) that bundles all runtime-specific knowledge — `RuntimeKind`, capabilities, and parser factories — into one adapter class per runtime. The factory depends on the `RuntimeProvider` port, not on concrete registries.

The key architectural shift: instead of the factory knowing "Docker has these capabilities and these parsers", the factory says "give me whatever `RuntimeProvider` says Docker needs." Adding a new runtime collapses from 17 files to 1 new adapter class + 1 registration line.

**Create** `ports/provider.py` — RuntimeProvider ABC:
```python
from abc import ABC, abstractmethod

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.factory import Parsers


class RuntimeProvider(ABC):
    """Port: encapsulates all runtime-specific knowledge.

    Pure abstraction — no I/O, no side effects, no adapter imports.
    The factory depends on this port, not on concrete registries.
    """

    @property
    @abstractmethod
    def kind(self) -> RuntimeKind:
        """Return the RuntimeKind enum member for this runtime."""

    @abstractmethod
    def capabilities(self) -> RuntimeCapabilities:
        """Return the capabilities for this runtime."""

    @abstractmethod
    def create_parsers(self) -> Parsers:
        """Create and return parser instances for this runtime."""
```

**Create** `adapters/provider/__init__.py` — empty init for new adapter package.

**Create** `adapters/provider/docker.py`:
```python
from oci_runtime.adapters.parser.docker import (
    DockerContainerParser, DockerImageParser,
    DockerNetworkParser, DockerVolumeParser,
)
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.factory import Parsers
from oci_runtime.ports.provider import RuntimeProvider


class DockerRuntimeProvider(RuntimeProvider):
    @property
    def kind(self) -> RuntimeKind:
        return RuntimeKind.DOCKER

    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            supported_output_formats=["json", "yaml"],
            needs_userns_keep_id=False,
            supports_log_drivers=True,
            tar_entry_name="Dockerfile",
        )

    def create_parsers(self) -> Parsers:
        return Parsers(
            cp=DockerContainerParser(), ip=DockerImageParser(),
            vp=DockerVolumeParser(), np=DockerNetworkParser(),
        )
```

**Create** `adapters/provider/podman.py`:
```python
from oci_runtime.adapters.parser.podman import (
    PodmanContainerParser, PodmanImageParser,
    PodmanNetworkParser, PodmanVolumeParser,
)
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.factory import Parsers
from oci_runtime.ports.provider import RuntimeProvider


class PodmanRuntimeProvider(RuntimeProvider):
    @property
    def kind(self) -> RuntimeKind:
        return RuntimeKind.PODMAN

    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            supported_output_formats=["json"],
            needs_userns_keep_id=True,
            supports_log_drivers=False,
            tar_entry_name="Containerfile",
            default_run_flags=["--userns=keep-id"],
        )

    def create_parsers(self) -> Parsers:
        return Parsers(
            cp=PodmanContainerParser(), ip=PodmanImageParser(),
            vp=PodmanVolumeParser(), np=PodmanNetworkParser(),
        )
```

**Update** `factory.py` — Replace registries + free functions with provider registry:

1. Add `from oci_runtime.domain.enums import RuntimeKind` import (already present).

2. Add module-level registry + registration functions — `register_provider` is single-arg since the provider self-reports its `kind`:
```python
_PROVIDER_REGISTRY: dict[RuntimeKind, RuntimeProvider] = {}


def register_provider(provider: RuntimeProvider) -> None:
    kind = provider.kind
    if kind in _PROVIDER_REGISTRY:
        raise ValueError(f"Provider for '{kind.value}' is already registered")
    _PROVIDER_REGISTRY[kind] = provider


def get_provider(kind: RuntimeKind) -> RuntimeProvider:
    try:
        return _PROVIDER_REGISTRY[kind]
    except KeyError:
        raise NotImplementedError(
            f"No RuntimeProvider registered for RuntimeKind: {kind}. "
            f"Registered: {list(_PROVIDER_REGISTRY.keys())}"
        )
```

3. Register built-in providers at module level:
```python
from oci_runtime.adapters.provider.docker import DockerRuntimeProvider
from oci_runtime.adapters.provider.podman import PodmanRuntimeProvider

register_provider(DockerRuntimeProvider())
register_provider(PodmanRuntimeProvider())
```

4. Remove `_CAPABILITY_REGISTRY`, `_PARSER_REGISTRY`, `build_capabilities()`, `build_parsers()`, `_load_docker_parsers()`, and `_load_podman_parsers()` entirely. Update `RuntimeFactory.create()` to use the provider directly:
```python
class RuntimeFactory:
    def create(self, preference: RuntimePreference) -> ContainerEngine:
        binary = preference.get_binary()
        transport = self._cfg.transport_factory(binary)
        provider = get_provider(preference.kind)
        caps = provider.capabilities()
        parsers = provider.create_parsers()
        ...
```

5. Update `_default_parser_provider` similarly:
```python
def _default_parser_provider(kind: RuntimeKind) -> Parsers:
    return get_provider(kind).create_parsers()
```

**Update** `engines.py` — Remove `EngineProfile` objects (`docker`, `podman`) since these were only used as arguments to the now-removed `build_capabilities()`/`build_parsers()`. Also remove the `EngineProfile` import. Keep `RuntimePreference` objects (`docker_pref`, `podman_pref`) as they remain the public API for consumers to pass to `RuntimeFactory.create()`. The file becomes:
```python
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimePreference

docker_pref = RuntimePreference(kind=RuntimeKind.DOCKER)
podman_pref = RuntimePreference(kind=RuntimeKind.PODMAN)
```

#### Tests to Add/Update

**`tests/unit/ports/test_provider.py`** — NEW, 5 tests:
- `test_runtime_provider_is_abc` — ABC cannot be instantiated directly
- `test_runtime_provider_has_three_abstract_methods` — `kind`, `capabilities`, `create_parsers` are abstract
- `test_provider_importable_from_port` — `from oci_runtime.ports.provider import RuntimeProvider`

**`tests/unit/adapters/test_providers.py`** — NEW, ~25 tests:
- `TestDockerRuntimeProvider`: kind, capabilities (permanent field-value assertions — `tar_entry_name == "Dockerfile"`, `needs_userns_keep_id is False`, `supports_log_drivers is True`, `default_run_flags == []`), parsers (type identity with port ABCs), hexagonal compliance
- `TestPodmanRuntimeProvider`: same structure with Podman-specific field values (`tar_entry_name == "Containerfile"`, `needs_userns_keep_id is True`, `supports_log_drivers is False`, `default_run_flags == ["--userns=keep-id"]`)
- `TestProviderRegistry`: register, get, unknown kind raises NotImplementedError, duplicate registration raises ValueError

**`tests/unit/adapters/test_factory.py`** — Remove `TestBuildCapabilities` and `TestBuildParsers` (both classes tested the removed functions). Remove `_FakeRuntimeKind` helper class (no longer needed). Keep `TestRuntimeFactoryCreate` (factory still works — `RuntimeFactory.create()` internally uses `get_provider(kind).capabilities()` via provider).

**`tests/integration/capability/test_capabilities.py`** — Significant rewrite:
- Remove `TestCapabilityValues` (12 test methods) — all capability value assertions migrated to `tests/unit/adapters/test_providers.py` as permanent field-value assertions on provider classes (see above).
- Remove `test_build_capabilities_unknown_kind_raises_not_implemented` — covered by `TestProviderRegistry` in unit tests.
- Remove `test_build_capabilities_accepts_engine_profile` — `build_capabilities` no longer exists, and `EngineProfile` objects are removed from `engines.py`.
- Keep `TestCapabilityEdgeCases` tests that are not about `build_capabilities`: `test_runtime_capabilities_mutable`, `test_runtime_capabilities_default_output_format`, `test_runtime_preference_is_frozen`, `test_runtime_preference_custom_binary`, `test_runtime_preference_no_binary_uses_kind_value`, `test_cli_runtime_info_uses_supported_formats`, `test_cli_runtime_info_skips_format_if_not_supported`.

**`tests/integration/functional/conftest.py`** — Update `docker_caps` fixture: replace `build_capabilities(docker_pref)` with a direct `RuntimeCapabilities(...)` construction or a provider call. The fixture's purpose is to provide capabilities for functional tests — it doesn't need to go through the now-removed factory function.

**`tests/integration/integration/test_factory_wiring.py`** — Remove imports of `build_capabilities` and `build_parsers` (line 25). Add `test_provider_registration_does_not_break_factory` — smoke test that factory still works after provider registration.

**`tests/unit/adapters/test_engines.py`** — Remove assertions on `engines.docker`/`engines.podman` (removed from `engines.py`). Keep assertions on `engines.docker_pref`/`engines.podman_pref`.

**`tests/unit/ports/test_capabilities.py`** — `EngineProfile` dataclass tests remain unchanged. The `EngineProfile` class stays in `ports/capabilities.py` — it's a valid port type, just no longer used by `build_capabilities`/`build_parsers`.

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|---|---|---|
| Domain: pure Python, no I/O | ✅ Unchanged | `RuntimeKind` enum unchanged. No domain types modified. |
| Ports: ABCs only, no implementation | ✅ | `RuntimeProvider` has 3 abstract methods — pure contract, no concrete code |
| Ports: No adapter imports | ✅ | `RuntimeProvider` imports only from `ports/` — `RuntimeCapabilities` and `Parsers` are port types |
| Ports: no intermediate free functions | ✅ | No `build_capabilities()`/`build_parsers()` wrappers — factory depends directly on `RuntimeProvider` port |
| Adapters: implement port contracts | ✅ | `DockerRuntimeProvider`/`PodmanRuntimeProvider` both subclass `RuntimeProvider` |
| Adapters: contain all I/O and runtime-specific knowledge | ✅ | Eager parser imports at top of provider file (no cyclic dependency — provider is a new package, not factory.py) |
| Factory: depends on abstractions, not concretions | ✅ | Factory calls `get_provider()` returning `RuntimeProvider` — never references `DockerRuntimeProvider` by name |
| Factory: zero runtime-specific strings | ✅ | No `"docker"`, `"podman"`, `"Dockerfile"`, `"Containerfile"` in factory logic |
| Factory: OCP compliant | ✅ | Adding `nerdctl` = 1 new provider class + 1 `register_provider()` call — **zero edits to factory.py** |
| New runtime process | ✅ | Collapsed from 17 files → 1 new file + 1 registration line (see comparison table below) |
| Registry key: `RuntimeKind` | ✅ | Type-safe, trivially additive for new runtimes (add enum member + provider) — still eliminates 16 of 17 file changes |

#### Effort Comparison: Adding nerdctl

| Concern | Current Architecture | With RuntimeProvider Port |
|---------|---------------------|--------------------------|
| Source files to edit | 7 source files (`enums.py`, `engines.py`, `factory.py`, `ports/capabilities.py`, etc.) | `domain/enums.py` — add 1 enum member (trivially additive, cannot be avoided). `engines.py` — remove `EngineProfile` objects, keep `RuntimePreference` constants. |
| Source files to create | `adapters/parser/nerdctl.py` | `adapters/provider/nerdctl.py` (1 file only) |
| Lines of change | Scattered across 7 source files | `RuntimeKind.NERDCTL = "nerdctl"` + one new provider class + `register_provider(NerdctlRuntimeProvider())` |
| Test files to update | 10 test files | **Zero** (provider tests cover the new class independently) |
| Risk of missed reference | High (89 `RuntimeKind` refs) | None (knowledge is encapsulated in the provider adapter) |
| Total file touch count | **17 existing files** + 2 new files | **1 existing file** (1-line enum addition) + 1 new file |

#### Prototype Validation

**Files:**
- `dev/validation/oci_runtime/finding-10-runtime-provider.py` — validates approach, hexagonal compliance, nerdctl addition (54 tests)
- `dev/validation/oci_runtime/finding-10-equivalence-validation.py` — validates behavioral equivalence with current factory (95 tests)

**Results:** 149/149 tests pass. Provider capabilities match `build_capabilities()` value-for-value. Provider parser types are identical to `build_parsers()` output. New runtime addition demonstrated with `NerdctlRuntimeProvider` — zero changes to factory code.

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-05-31
**Changes applied:**

1. **`ports/provider.py`** — Created `RuntimeProvider` ABC port with 3 abstract methods: `kind` property, `capabilities()`, and `create_parsers()`. Pure abstraction with no adapter dependencies — factory now depends on the provider port instead of concrete registries.

2. **`adapters/provider/__init__.py`** — Created empty init for new `adapters/provider/` package.

3. **`adapters/provider/docker.py`** — Created `DockerRuntimeProvider` implementing `RuntimeProvider` with `RuntimeKind.DOCKER`, Docker-specific `RuntimeCapabilities` (`tar_entry_name="Dockerfile"`, `needs_userns_keep_id=False`, `supports_log_drivers=True`, `supported_output_formats=["json", "yaml"]`), and parser factory returning `DockerContainerParser`, `DockerImageParser`, `DockerVolumeParser`, `DockerNetworkParser`.

4. **`adapters/provider/podman.py`** — Created `PodmanRuntimeProvider` implementing `RuntimeProvider` with `RuntimeKind.PODMAN`, Podman-specific `RuntimeCapabilities` (`tar_entry_name="Containerfile"`, `needs_userns_keep_id=True`, `supports_log_drivers=False`, `default_run_flags=["--userns=keep-id"]`), and parser factory returning `PodmanContainerParser`, `PodmanImageParser`, `PodmanNetworkParser`, `PodmanVolumeParser`.

5. **`factory.py`** — Replaced `_CAPABILITY_REGISTRY` + `_PARSER_REGISTRY` + `build_capabilities()` + `build_parsers()` + `_load_docker_parsers()` + `_load_podman_parsers()` with `_PROVIDER_REGISTRY` dict, `register_provider()`, and `get_provider()` functions. Built-in providers registered at module level. `RuntimeFactory.create()` now calls `get_provider(preference.kind)` then `provider.capabilities()` and `provider.create_parsers()`. `_default_parser_provider()` delegates to `get_provider(kind).create_parsers()`.

6. **`engines.py`** — Removed `docker` and `podman` `EngineProfile` objects (no longer needed). Kept `docker_pref` and `podman_pref` `RuntimePreference` constants as the public API for `RuntimeFactory.create()`.

7. **`tests/unit/ports/test_provider.py`** — Added 9 tests: ABC cannot be instantiated directly, 3 abstract methods present (`kind`, `capabilities`, `create_parsers`), method signatures correct, concrete subclass must implement all 3 abstract methods, complete implementation can be instantiated and returns correct types.

8. **`tests/unit/adapters/test_providers.py`** — Added 33 tests: `TestDockerRuntimeProvider` (10 tests — kind, capability values, parser types, idempotency), `TestPodmanRuntimeProvider` (10 tests — same structure with Podman-specific values), `TestDockerProviderParserTypes` (4 tests — concrete Docker parser type identity), `TestPodmanProviderParserTypes` (4 tests — concrete Podman parser type identity), `TestProviderRegistry` (5 tests — `get_provider` for Docker/Podman, unknown kind raises `NotImplementedError`, duplicate registration raises `ValueError`, all registered kinds return correct `kind`).

9. **`tests/unit/adapters/test_factory.py`** — Removed `TestBuildCapabilities` (4 tests), `TestBuildParsers` (3 tests), and `_FakeRuntimeKind` helper class. Kept `TestRuntimeFactoryCreate` (3 tests) — factory still works with `RuntimeFactory.create()` internally using provider.

10. **`tests/unit/adapters/test_engines.py`** — Updated 4 tests to reference `docker_pref`/`podman_pref` instead of removed `docker`/`podman` `EngineProfile` objects.

11. **`tests/integration/capability/test_capabilities.py`** — Removed `TestCapabilityValues` (12 tests — capability value assertions migrated to `test_providers.py`). Removed `test_build_capabilities_unknown_kind_raises_not_implemented` and `test_build_capabilities_accepts_engine_profile`. Kept 7 edge case tests in `TestCapabilityEdgeCases`.

12. **`tests/integration/functional/conftest.py`** — Replaced `build_capabilities(docker_pref)` fixture with `DockerRuntimeProvider().capabilities()`.

13. **`tests/integration/integration/test_factory_wiring.py`** — Removed imports of `build_capabilities` and `build_parsers` (line 25).

**Solution rationale:** Replaced two separate registries (`_CAPABILITY_REGISTRY` + `_PARSER_REGISTRY`) that had to be manually kept in sync with a single `RuntimeProvider` ABC per runtime. The factory now depends on the `RuntimeProvider` port, satisfying OCP: adding `nerdctl` requires 1 new provider class + 1 `register_provider()` call — zero edits to factory logic. The `EngineProfile` class is retained in `ports/capabilities.py` as a valid port type (no longer used by factory internals).

**Verification:** 577 tests pass (0 failures, 42 new tests across 2 new test files, 19 removed tests from refactored files). All provider capabilities match the original `_CAPABILITY_REGISTRY` values. All provider parser types match `_PARSER_REGISTRY` output. OCP compliance confirmed: adding a new runtime requires only 1 new adapter file + 1 registration line, down from 17 files.

---

### Finding #11: Tests Bypass Port Abstractions [RESOLVED]

**Files:** Multiple test files in `tests/unit/adapters/`

**Code pattern:**
```python
from oci_runtime.adapters.managers.container import CliContainerManager  # concrete class
```

**Problem:** Unit tests import and test concrete `Cli*` adapter classes directly instead of testing through abstract port interfaces. While contract tests (`test_interface_compliance.py`) verify ABC implementation, the behavior tests couple to `CliContainerManager`, `CliVolumeManager`, etc. directly. Swapping adapters (e.g., from CLI to HTTP API) would require rewriting all behavior tests.

**Deep Investigation — Nuanced Finding:**

After tracing every test file in the module (40 test files across unit, integration, contract, and smoke suites), the actual coupling has three distinct levels:

**Level 1 — Unit adapter tests (7 files, ~650 lines, GOOD pattern):**
Files like `test_cli_volume_manager.py`, `test_cli_container_manager.py`, `test_cli_image_manager.py`, `test_cli_network_manager.py`, `test_cli_runtime.py`, `test_discovery.py`, `test_providers.py` already use the correct hexagonal pattern — they import only the one concrete class under test and mock all port dependencies with `MagicMock(spec=Transport)`. No refactoring needed here.

**Level 2 — Integration tests (8 files + 1 conftest, ~1,300 lines, COUPLED):**
`test_manager_commands.py`, `test_workflows.py` + `functional/conftest.py`, `test_error_conditions.py`, `test_malformed_output.py`, `test_empty_outputs.py`, `test_concurrency.py`, `test_capabilities.py` wire the full concrete Docker adapter stack — `CliContainerManager(DockerContainerParser(), ...)` — hardcoding Docker-specific parsers, commands, and output formats. These would break if a new runtime (nerdctl, Finch) was added or the adapter constructor changed.

**Level 3 — Parser tests (2 files, ~486 lines, ACCEPTABLE):**
`test_docker_parser.py` and `test_podman_parser.py` test pure string parsing and must be concrete by nature. These stay as-is.

**Additional DRY violation:** 5+ test files define near-identical inline `_MockParser` stubs for the same port ABCs. Each copy differs only in return values, creating maintenance duplication.

---

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-06-01
**Changes applied:**

1. **`tests/__init__.py`** — Created to make `tests` a Python package for cross-directory imports
2. **`tests/helpers/__init__.py`** — Created empty init for helpers package
3. **`tests/helpers/mock_parsers.py`** — Created with 4 mock parser classes (`MockContainerParser`, `MockImageParser`, `MockVolumeParser`, `MockNetworkParser`) implementing each port ABC, with predetermined return values and `is_not_found_error` patterns matching the Docker parsers (including `"pull access denied"` for images and `"No such object"` for containers)
4. **`tests/helpers/mock_transport.py`** — Created with `RecordingTransport` (extracted from conftest with `on_output` kwarg added), `FailingTransport` (new, for error-path contract tests), and `RecordedCall` dataclass
5. **`tests/unit/ports/test_container_manager_contract.py`** — 15 behavioral contract tests via abstract `ContainerManagerContractTest` base class + `TestCliContainerManagerContract` concrete subclass
6. **`tests/unit/ports/test_image_manager_contract.py`** — 13 behavioral contract tests
7. **`tests/unit/ports/test_volume_manager_contract.py`** — 8 behavioral contract tests
8. **`tests/unit/ports/test_network_manager_contract.py`** — 10 behavioral contract tests
9. **`tests/integration/functional/conftest.py`** — Replaced `Docker*Parser` with `Mock*Parser`; replaced `DockerRuntimeProvider().capabilities()` with `RuntimeCapabilities()` defaults
10. **`tests/integration/integration/test_manager_commands.py`** — Replaced `Docker*Parser` with `Mock*Parser`; updated 6 parser-value-dependent assertions; migrated `ExecResult` import from conftest re-export to `oci_runtime.ports.transport`
11. **`tests/integration/functional/test_workflows.py`** — Replaced Docker parsers via conftest; updated 5 parser-value-dependent assertions; migrated `ExecResult` import to canonical path
12. **`tests/integration/boundary/test_concurrency.py`** — Replaced `DockerContainerParser` with `MockContainerParser`; updated `info.id` assertion to mock value
13. **`tests/integration/capability/test_capabilities.py`** — Removed unused Docker parser imports; migrated `ExecResult`/`RecordingTransport` imports
14. **`tests/integration/boundary/test_error_conditions.py`** — Migrated imports only (kept real parsers — tests depend on parser error-detection behavior)
15. **`tests/integration/boundary/test_malformed_output.py`** — Migrated imports only (kept real parsers — tests depend on parse-failure behavior)
16. **`tests/integration/boundary/test_empty_outputs.py`** — Migrated imports only (kept real parsers — tests depend on empty-parse behavior)
17. **`tests/integration/integration/test_engine_lifecycle.py`** — Migrated `RecordingTransport` import to helpers
18. **`tests/integration/integration/test_factory_wiring.py`** — Migrated `RecordingTransport` import to helpers
19. **`tests/integration/contract/test_interface_compliance.py`** — Migrated `RecordingTransport` import to helpers
20. **`pyproject.toml`** — Added `"."` to `pythonpath` for test module resolution
21. **`tests/integration/conftest.py`** — Stripped to `import pytest` only; removed `RecordedCall`, `RecordingTransport`, and dead `recording_transport` fixture (all migrated to `tests/helpers/mock_transport.py` with no backward compat shim)

**Key decisions during TDD implementation:**
- `RecordingTransport` in helpers includes the `on_output` kwarg (missing in conftest version — LSP violation)
- Mock parsers match Docker `is_not_found_error` patterns (without this, error-propagation tests break)
- 3 integration files kept real parsers (`test_malformed_output.py`, `test_empty_outputs.py`, `test_error_conditions.py`) — their tests depend on parse-failure behavior that mocks cannot replicate
- No backward compat shim for `RecordingTransport` in conftest — all consumers migrated in one pass

**Solution rationale:** Extracted shared test doubles into `tests/helpers/` to eliminate inline stubs. Added behavioral port contract tests as abstract base classes (port-level) with concrete adapter subclasses. Integration tests use mock parsers for manager-level behavior and keep real parsers where parse-failure is under test. Unit adapter tests (7 files) were already correct and unchanged.

**Verification:** 613 tests pass (0 failures). 46 new contract tests added.

### Finding #12: `ContainerInfo.state` Typed as `str` Instead of `ContainerState`

**File:** `domain/types.py:86`

**Code:**
```python
@dataclass
class ContainerInfo:
    ...
    state: str    # should this be ContainerState?
```

**Relationship to Finding #8:** Directly related.

**Analysis:** `ContainerInfo.state` is typed as `str` because:
1. The `ContainerState` enum (Finding #8) only has 3 values (`CREATED`, `RUNNING`, `STOPPED`)
2. Docker/Podman return 7 distinct status strings, including `"paused"`, `"removing"`, `"exited"`, `"dead"` which don't exist in the enum
3. If `state` were typed as `ContainerState`, parsers would silently pass non-enum strings (Python dataclasses don't validate at runtime) — the type annotation would be a lie
4. The `RunConfig` dataclass already demonstrates the correct pattern: `str | Enum` union types for `network` and `restart_policy`

**Fix:** Either expand `ContainerState` to 7 values and type `state: ContainerState`, or explicitly document the `str` typing as intentional (raw pass-through from engine JSON).

### Proposed Solution

#### Approach: Combined with Finding #8 — type `state` as `ContainerState`

The `ContainerState` expansion to `StrEnum` (Finding #8) directly resolves this finding. Change `ContainerInfo.state` from `str` to `ContainerState`. Because `StrEnum` members ARE strings, all existing comparisons (`info.state == "running"`) continue to work without modification.

**Change** `domain/types.py:86`:
```python
state: ContainerState
```

#### Tests to Add/Update

**`tests/unit/domain/test_types.py`** — Add `test_state_is_typed_as_container_state` confirming `ContainerInfo.state` field type is `ContainerState`.

**No changes needed** to parser tests or workflow tests — `StrEnum` IS `str`, so all existing `info.state == "running"` comparisons continue to work without modification.

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|---|---|---|
| Domain: pure Python, no I/O | ✅ Unchanged | `ContainerState` is a `StrEnum` from stdlib |
| Ports: ABCs only, no implementation | ✅ Unchanged | `ContainerParser` contracts unchanged — still return `ContainerInfo` |
| Adapters: implement contracts, map at boundary | ✅ | `ContainerState(value)` wrapping in parsers is adapter-layer concern |
| Factory: only DI composition root | ✅ Unchanged | No factory changes needed |
| Backward compatible | ✅ | `StrEnum` IS `str` — all existing comparisons work |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-05-31
**Changes applied:**

1. **`domain/types.py:86`** — Changed `ContainerInfo.state` type annotation from `str` to `ContainerState` (7-value `StrEnum`).

Resolved together with Finding #8 — see Finding #8 Resolution for the full changes to `domain/enums.py`, parser files, and test files.

**Solution rationale:** The `ContainerState` expansion to `StrEnum` (Finding #8) enabled typing `ContainerInfo.state` as the domain enum instead of raw `str`. `StrEnum` members ARE strings, so all existing comparisons work without modification.

**Verification:** 560/560 tests pass (0 failures). `test_state_is_typed_as_container_state` confirms the field type is `ContainerState`.

---

### Finding #21: `CliBaseManager._check_result` Uses `hasattr` Circumventing Type Safety

**File:** `adapters/managers/base.py:47-48`

**Code:**
```python
def _check_result(self, result, cmd, *, operation, entity, not_found):
    ...
    stderr_str = result.stderr.decode("utf-8", errors="replace")

    # Parser is expected to have an is_not_found_error method
    if hasattr(self._parser, "is_not_found_error") and self._parser.is_not_found_error(stderr_str):
        raise not_found(entity)
    ...
```

**Problem:** The `hasattr` check is a dynamic type interrogation that bypasses the type system. The generic parameter `P` on `CliBaseManager[P]` is supposed to guarantee that the parser implements `is_not_found_error` (all 4 port ABCs define it as `@abstractmethod`). If the type system is trusted, `hasattr` is dead code that masks configuration errors.

**Architectural drift:** In clean hexagonal architecture, the base class should be able to call `self._parser.is_not_found_error(stderr_str)` unconditionally — the type parameter provides the guarantee. The `hasattr` guard suggests either:
- The author didn't trust the generic type parameter
- The generic was added later and the guard is leftover paranoia
- There was once a code path where `_parser` could be a non-parser object

**Impact:** If a developer creates a `CliBaseManager[str]` (with `str` as the parser type), `hasattr(str, "is_not_found_error")` is `False`, and the "not found" detection is silently skipped — every error gets classified as `ContainerRuntimeError` instead of the specific `*NotFoundError`. The error is silently degraded rather than loudly failing.

**Fix:** Remove the `hasattr` guard and call `self._parser.is_not_found_error()` directly. If a type error occurs, it will be caught at type-check time (mypy/pyright) or crash loudly at runtime with `AttributeError`, which is strictly better than silent degradation.

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-06-03
**Changes applied:**

1. **`adapters/managers/base.py:47`** — Removed `hasattr(self._parser, "is_not_found_error")` guard; now calls `self._parser.is_not_found_error(stderr_str)` directly. The type system (`Generic[P]`) guarantees `P` implements the method via port ABC contract.

**Solution rationale:** The `hasattr` guard was leftover paranoia that silently degraded type errors. All 4 port ABCs (`ContainerParser`, `ImageParser`, `VolumeParser`, `NetworkParser`) declare `is_not_found_error` as `@abstractmethod`, and all 8 concrete parsers implement it. Removing the guard means type mismatches are caught at type-check time or crash loudly with `AttributeError` — strictly better than silent fallback.

**Verification:** 641/641 tests pass (0 failures).

---

### Finding #22: `ContainerManager.exec()` Returns Bare `tuple[int, str]`, Silently Drops stderr

**File:** `ports/managers.py:70`, `adapters/managers/container.py:169-179`

**Code (port):**
```python
class ContainerManager(ABC):
    @abstractmethod
    def exec(self, container: str, command: list[str],
             detach: bool = False, user: str | None = None) -> tuple[int, str]: ...
```

**Code (adapter):**
```python
def exec(self, container, command, detach=False, user=None):
    ...
    result = self._transport.execute(cmd)
    self._check_result(result, cmd, ...)
    return (result.returncode, self._decode_stdout(result.stdout))
```

**Problem:** The return type `tuple[int, str]` only carries the exit code and stdout. stderr is silently discarded. If a command fails with a meaningful error message on stderr, the caller never sees it.

**Architectural drift:** Returning a bare tuple instead of a domain type is a hexagonal architecture smell. The `PortMapping`, `ExecResult`, and `RunConfig` types all demonstrate the correct pattern — rich dataclasses with named fields.

**Fix:** Define a `ExecOutput` dataclass in `domain/types.py`:
```python
@dataclass
class ExecOutput:
    returncode: int
    stdout: str
    stderr: str
```

Update the port signature and adapter to return `ExecOutput` instead of `tuple[int, str]`. This preserves the stderr information and gives callers named access to all three fields.

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-06-03
**Changes applied:**

1. **`domain/types.py`** — Added `ExecOutput` dataclass with `returncode: int`, `stdout: str`, `stderr: str`.
2. **`ports/managers.py:72`** — Changed `exec()` return type from `tuple[int, str]` to `ExecOutput`; added import.
3. **`adapters/managers/container.py:201-215`** — Changed `exec()` return from `(result.returncode, self._decode_stdout(result.stdout))` to `ExecOutput(returncode=..., stdout=..., stderr=...)`.

**Solution rationale:** Returning a bare `tuple[int, str]` silently dropped stderr — callers had no way to see command errors on stderr. Replaced with `ExecOutput` domain type following the pattern established by `ExecResult`, `RunConfig`, `PortMapping`, and other rich dataclasses. All callers access `.returncode`, `.stdout`, `.stderr` by name.

**Verification:** 641/641 tests pass (0 failures). Contract test `test_exec_returns_exec_output` explicitly asserts `ExecOutput` type and verifies all 3 fields.

---

## 🔵 LOW-SEVERITY / TECHNICAL DEBT

### Finding #13: Podman `parse_build_output` Too Simplistic

**File:** `adapters/parser/podman.py:177-178`

**Code (Podman):**
```python
def parse_build_output(self, raw: str) -> str:
    return raw.strip().splitlines()[-1].strip() if raw.strip() else ""
```

**Comparison (Docker):**
```python
def parse_build_output(self, raw: str) -> str:
    match = re.search(r"Successfully built ([a-f0-9]+)", raw)
    if match:
        return match.group(1)
    return ""
```

**Problem:** Podman's implementation assumes the image ID is always the last line of output. This is fragile in multiple scenarios:
1. **Warnings after the image ID** — e.g. `WARNING: Some post-build warning` would be returned as the image ID
2. **Info messages after the image ID** — future Podman versions might add informational lines
3. **Empty build output** — returns `""` correctly, but would fail on e.g. `\n\n\n` (whitespace-only)

**Deep Investigation — Correct Approach:**

**What Podman build output actually looks like (no `-q`):**
```
STEP 1/3: FROM alpine:latest
STEP 2/3: RUN echo hello
STEP 3/3: CMD ["sh"]
COMMIT
--> 789abc456def...789abc456def
Successfully tagged localhost/myimage:latest
789abc456def...789abc456def
```

The last line IS the 64-char hex image ID in the standard case, but the `Successfully tagged` line could be the last line if the image ID is absent.

**What `podman build -q` outputs:**
```
789abc456def...789abc456def
```

Just the bare hex ID on stdout. All progress goes to stderr.

**Recommended fix (Option A — best):** Add `--quiet` to `default_build_flags` for both runtimes and simplify parsers:
```python
# In factory.py:
RuntimeCapabilities(..., default_build_flags=["--quiet"], ...)

# Docker parser:
def parse_build_output(self, raw: str) -> str:
    raw = raw.strip()
    return raw.removeprefix("sha256:") if raw else ""

# Podman parser:
def parse_build_output(self, raw: str) -> str:
    return raw.strip()
```

**Alternative fix (Option B — parser-only):** Replace the last-line heuristic with a multi-strategy regex:
```python
def parse_build_output(self, raw: str) -> str:
    if not raw.strip():
        return ""
    # Look for "Successfully built" (Docker-compatible)
    match = re.search(r"Successfully built ([a-f0-9]+)", raw)
    if match:
        return match.group(1)
    # Find a 64-char hex string on its own line (primary Podman format)
    match = re.search(r"^([a-f0-9]{64})$", raw, re.MULTILINE)
    if match:
        return match.group(1)
    # Fallback: any hex string 12+ chars on its own line
    match = re.search(r"^([a-f0-9]{12,})$", raw, re.MULTILINE)
    return match.group(1) if match else ""
```

The manager module (`CliImageManager.build()`) does not pass `--quiet`, so the default build output is verbose for both runtimes.

### Proposed Solution

#### Approach: `--quiet` in `default_build_flags` + simplified parsers

Add `--quiet` to `default_build_flags` in both `DockerRuntimeProvider` and `PodmanRuntimeProvider`. This makes `docker build` / `podman build` output deterministic — just the bare image hash on stdout — instead of verbose multi-line output that requires fragile parsing.

Both parsers are simplified to `raw.strip().removeprefix("sha256:")`, suitable for the deterministic `--quiet` output format. The same parser works for both runtimes.

**Update** `adapters/provider/docker.py` — Add `default_build_flags=["--quiet"]` to `RuntimeCapabilities`:
```python
return RuntimeCapabilities(
    supported_output_formats=["json", "yaml"],
    needs_userns_keep_id=False,
    supports_log_drivers=True,
    tar_entry_name="Dockerfile",
    default_build_flags=["--quiet"],
)
```

**Update** `adapters/provider/podman.py` — Add `default_build_flags=["--quiet"]`:
```python
return RuntimeCapabilities(
    supported_output_formats=["json"],
    needs_userns_keep_id=True,
    supports_log_drivers=False,
    tar_entry_name="Containerfile",
    default_run_flags=["--userns=keep-id"],
    default_build_flags=["--quiet"],
)
```

**Update** `adapters/parser/docker.py` — Replace regex with simple strip:
```python
def parse_build_output(self, raw: str) -> str:
    return raw.strip().removeprefix("sha256:")
```

**Update** `adapters/parser/podman.py` — Replace last-line heuristic with same:
```python
def parse_build_output(self, raw: str) -> str:
    return raw.strip().removeprefix("sha256:")
```

#### Tests to Update

**`tests/unit/adapters/test_docker_parser.py`** — Change test input from verbose format to bare hash:
```python
def test_parse_build_output(self):
    image_id = self.parser.parse_build_output("abc123def456\n")
    assert image_id == "abc123def456"
```

**`tests/integration/integration/test_manager_commands.py:43`** — Update mock key and response:
```
"docker build --quiet -t myimg -": ExecResult(0, b"abc123\n", b"")
```

**`tests/integration/functional/test_workflows.py:70,82`** — Same pattern for both build mocks:
```
f"docker build --quiet -t myimg -": ExecResult(0, b"buildabc123\n", b"")
f"docker build --quiet -t myimg -f {dfile} {tmp_path}": ExecResult(0, b"def456\n", b"")
```

**`tests/unit/ports/test_image_manager_contract.py:36,98`** — Same mock key update:
```
"docker build --quiet -t myimg -": ExecResult(0, b"sha256:abc\n", b"")
```

#### Files Verified as Unaffected

| File | Reason |
|------|--------|
| `adapters/parser/podman.py` test | Already uses bare hash `"abc123def456\n"` — passes unchanged |
| `tests/unit/adapters/test_cli_image_manager.py` | Uses `MockImageParser` (fixed return) — unaffected |
| `tests/helpers/mock_parsers.py` | Mock returns fixed `"sha256:abc"` regardless of input |
| `tests/unit/ports/test_parsers.py` | Tests `parse_build_output` is abstract — unaffected |
| `tests/integration/contract/test_interface_compliance.py` | Tests method name in set — unaffected |
| `tests/integration/integration/test_factory_wiring.py` | Stub parser — not testing parse logic |
| `tests/unit/ports/test_managers.py` / `test_provider.py` | Test doubles — unaffected |
| `ports/parsers.py` | ABC signature unchanged |
| `ports/capabilities.py` | `default_build_flags` field already exists |
| `adapters/managers/image.py` | Already reads `default_build_flags` dynamically |

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Domain: pure Python, no I/O | ✅ Unchanged | No domain types modified |
| Ports: ABCs only, no implementation | ✅ Unchanged | `ImageParser.parse_build_output` signature unchanged |
| Adapters: implement contracts, contain I/O | ✅ | All changes in providers + parsers (adapter layer) |
| Factory: only DI composition root | ✅ Unchanged | No factory wiring changes |
| Backward compatible | ✅ | `--quiet` only affects stdout; stderr (progress) still streams to terminal |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-06-02
**Changes applied:**

1. **`adapters/provider/docker.py`** — Added `default_build_flags=["--quiet"]` to `RuntimeCapabilities` constructor, so `docker build` output is deterministic (bare hash).
2. **`adapters/provider/podman.py`** — Added `default_build_flags=["--quiet"]` to `RuntimeCapabilities` constructor, so `podman build` output is deterministic (bare hash).
3. **`adapters/parser/docker.py`** — Simplified `parse_build_output` from regex (`re.search(r"Successfully built ([a-f0-9]+)", raw)`) to `raw.strip().removeprefix("sha256:")`, suitable for `--quiet` output.
4. **`adapters/parser/podman.py`** — Simplified `parse_build_output` from last-line heuristic (`raw.strip().splitlines()[-1].strip()`) to `raw.strip().removeprefix("sha256:")`, matching Docker parser.
5. **`tests/unit/adapters/test_docker_parser.py`** — Updated `test_parse_build_output` input from `"Successfully built abc123def456\n"` to `"sha256:abc123def456\n"`.
6. **`tests/unit/adapters/test_providers.py`** — Added `assert caps.default_build_flags == ["--quiet"]` to both `TestDockerRuntimeProvider.test_capabilities_values` and `TestPodmanRuntimeProvider.test_capabilities_values`.
7. **`tests/integration/integration/test_manager_commands.py`** — Updated `caps` fixture to `RuntimeCapabilities(default_build_flags=["--quiet"])`; updated build mock key and command assertion to include `--quiet` flag.
8. **`tests/integration/functional/conftest.py`** — Updated `docker_caps` fixture to `RuntimeCapabilities(default_build_flags=["--quiet"])`.
9. **`tests/integration/functional/test_workflows.py`** — Updated 2 build mock keys to include `--quiet` flag.
10. **`tests/unit/ports/test_image_manager_contract.py`** — Updated `_defaults` caps to include `default_build_flags=["--quiet"]`; updated 2 build mock keys to include `--quiet` flag.
11. **`tests/integration/boundary/test_malformed_output.py`** — Replaced `test_build_output_no_success_message` (which relied on old regex returning `""` for verbose output) with `test_build_output_empty` and `test_build_output_whitespace_only` using `--quiet` mode.

**Solution rationale:** Added `--quiet` to `default_build_flags` for both Docker and Podman providers, making build output deterministic (bare image hash) instead of verbose multi-line output that required fragile parsing. Both parsers are simplified to `raw.strip().removeprefix("sha256:")` — `--quiet` produces `sha256:abc...` for Docker and bare hex for Podman (where `removeprefix` is a no-op). The same parser works for both runtimes, eliminating the fragile last-line heuristic in Podman and the verbose-output regex in Docker. All test fixtures that exercise the build path were updated to include `--quiet` to match the new provider behavior.

**Verification:** 636 tests pass (0 failures) across unit and integration suites.

---

### Finding #14: Streaming Path File Descriptor Leak Risk

**File:** `adapters/transport/cli.py:48-102`

**Problem:** In the `subprocess.Popen` streaming path, if an exception occurs during the read loop:
1. The `finally` block (lines 92-95) closes the selector and pipes
2. But `process.wait()` on line 97 is never reached — the child becomes a zombie
3. If the exception happens before `selector.register()`, the selector/pipes may not be closed at all

The non-streaming path handles `subprocess.TimeoutExpired` (line 44-46) but the streaming path does not. A timeout during `process.wait(timeout=timeout)` on line 97 would leave the process unreaped.

### Proposed Solution

#### Approach: Extract `_read_stream()` + single outer `try/finally` for guaranteed process reaping

The current code mixes resource lifecycle (acquire Popen, wait for exit, close pipes) with data reading (selector loop) in nested try/finally blocks. The `process.wait()` is outside both inner try/finally blocks, so any exception in the read loop skips it, creating a zombie.

The fix separates concerns: **acquire** (`Popen`) → **operate** (`_read_stream()`) → **release** (`wait()` + close pipes), all in a single outer `try/finally`. A new `_read_stream()` helper owns only the selector lifecycle — it reads accumulated bytes and returns. The caller (the outer finally) guarantees the child is always reaped.

**Update** `adapters/transport/cli.py` — Extract read loop into `_read_stream()`:
```python
def _read_stream(
    self,
    process: subprocess.Popen,
    on_output: Callable[[bytes], None] | None = None,
) -> tuple[list[bytes], list[bytes]]:
    """Read stdout/stderr via selector until both pipes EOF.

    Extracted as a standalone method so its lifecycle is independent
    of Popen acquire/release. The caller owns the process lifecycle.
    """
    stdout_acc: list[bytes] = []
    stderr_acc: list[bytes] = []
    selector = selectors.DefaultSelector()
    try:
        selector.register(process.stdout, selectors.EVENT_READ)
        selector.register(process.stderr, selectors.EVENT_READ)
        while True:
            if process.poll() is not None and not selector.get_map():
                break
            if not selector.get_map():
                process.wait(timeout=0.1)
                continue
            events = selector.select(timeout=0.1)
            for key, _ in events:
                data = key.fileobj.read(1024)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                if key.fileobj is process.stdout:
                    stdout_acc.append(data)
                    if on_output:
                        on_output(data)
                else:
                    stderr_acc.append(data)
                    if on_output:
                        on_output(data)
    finally:
        selector.close()
    return stdout_acc, stderr_acc
```

**Restructure** `CliTransport.execute()` streaming path — single outer try/finally:
```python
# Streaming implementation using Popen
process = None
_stdin_thread: threading.Thread | None = None
try:
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if input_data else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    # stdin daemon thread (same as Fix 16b)
    if input_data:
        def _write_stdin() -> None:
            process.stdin.write(input_data)
            process.stdin.close()
        _stdin_thread = threading.Thread(target=_write_stdin, daemon=True)
        _stdin_thread.start()

    stdout_acc, stderr_acc = self._read_stream(process, on_output)

    if _stdin_thread:
        _stdin_thread.join(timeout=5)

    returncode = process.wait(timeout=timeout)
    return ExecResult(
        returncode=returncode,
        stdout=b"".join(stdout_acc),
        stderr=b"".join(stderr_acc),
    )

except FileNotFoundError:
    raise RuntimeNotAvailableError(self.binary) from None
except subprocess.TimeoutExpired:
    if process and process.poll() is None:
        process.kill()
        process.wait()
    raise
finally:
    # Guaranteed: child is always reaped regardless of exception path
    if process and process.poll() is None:
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    if process:
        for pipe in (process.stdout, process.stderr, process.stdin):
            if pipe:
                pipe.close()
```

#### Clarifications

1. **Only `FileNotFoundError`** — The restructured snippet catches `FileNotFoundError` (matching current lines 43 and 120), not `OSError`. `OSError` (permission denied, disk full) is a system-level failure that should propagate to the caller — it is not a "binary not available" situation. The non-streaming path also does not catch `OSError` (line 43), so this keeps both paths consistent.

2. **`_read_stream()` signature matches current code** — The signature `_read_stream(self, process, on_output=None) -> tuple[list[bytes], list[bytes]]` initializes `stdout_acc` and `stderr_acc` as plain `list[bytes]` inside the method, exactly matching the current code's initialization pattern. No behavioral difference — the two lists are populated identically in the selector loop and returned as a tuple for the caller to `b"".join()`.

3. **Test naming — rename existing, add new test class** — The existing `test_streaming_normal_case_unaffected` at `test_cli_transport.py` is renamed to `test_read_stream_normal_case` and moved under a new `TestReadStream` class (testing the extracted method directly). The new tests below are integration-level tests of the full `execute()` path. No duplicate coverage:

| Class | Test | What it validates |
|-------|------|-------------------|
| `TestReadStream` (renamed existing) | `test_read_stream_normal_case` | `_read_stream()` returns correct accumulated bytes |
| `TestExecuteStreaming` (new) | `test_read_exception_no_zombie` | Exception in read loop — child reaped |
| `TestExecuteStreaming` (new) | `test_timeout_expired_kills_process` | `process.wait()` timeout — child killed + reaped |
| `TestExecuteStreaming` (new) | `test_normal_execution` | Full streaming path works end-to-end |
| `TestExecuteStreaming` (new) | `test_stdin_large_input` | >64KB input, no deadlock |
| `TestExecuteStreaming` (new) | `test_selectors_cleaned_up` | All pipes closed after exception |

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Domain: pure Python, no I/O | ✅ Unchanged | No domain types modified |
| Ports: ABCs only, no implementation | ✅ Unchanged | `Transport.execute()` signature unchanged |
| Adapters: implement contracts, contain I/O | ✅ | `_read_stream()` is a private method of `CliTransport` — adapter layer |
| Adapters: orchestration only, no business logic | ✅ | Read → accumulate → return — no domain logic |
| Factory: only DI composition root | ✅ Unchanged | No factory wiring changes |
| Resource cleanup guaranteed | ✅ | Outer finally always reaps, regardless of exception path |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-06-02
**Changes applied:**

1. **`adapters/transport/cli.py`** — Extracted `_read_stream()` method (lines 18–57) owning only the selector lifecycle — reads bytes from stdout/stderr via selector, returns accumulated tuples. The caller (`execute()`) owns acquire/release of the `Popen` process.

2. **`adapters/transport/cli.py`** — Restructured `execute()` streaming path (lines 89–140) with a single outer `try/except/finally` guaranteeing the child process is always reaped. Uses a `_process_reaped` boolean flag to track whether reaping has already occurred in the normal path or `TimeoutExpired` handler.

3. **`adapters/transport/cli.py`** — Added `except subprocess.TimeoutExpired` handler in the streaming path that kills the child via `process.kill()` followed by `process.wait()` before re-raising.

4. **`adapters/transport/cli.py`** — The `finally` block checks the `_process_reaped` flag: if the process was never reaped (due to an unexpected exception in `_read_stream()` or `process.wait()`), it calls `process.kill()` + `process.wait()` and always closes all three pipes (`stdout`, `stderr`, `stdin`).

5. **`tests/unit/adapters/test_cli_transport.py`** — Replaced `test_streaming_normal_case_unaffected` (old inline test) with `TestReadStream.test_read_stream_normal_case` (direct `_read_stream()` unit test). Added `TestExecuteStreaming` class with 5 tests: `test_normal_execution`, `test_read_exception_no_zombie`, `test_timeout_expired_kills_process`, `test_stdin_large_input`, `test_selectors_cleaned_up`.

**Solution rationale:** Extracted the selector read loop into `_read_stream()` so its lifecycle is independent of `Popen` acquire/release. A single outer `try/except/finally` now wraps the entire streaming path, with a `_process_reaped` flag ensuring the child is always reaped regardless of which exception path is taken. `TimeoutExpired` is explicitly handled (kill + wait + re-raise), and the finally block cleans up all pipes in all cases.

**Verification:** 641 tests pass (0 failures) across unit and integration suites.

---

### Finding #15: Overly Broad `except Exception`

**Files:** `adapters/engine/cli.py:57,68,96,103`

**Code:**
```python
# CliRuntime.is_available() line 57:
except Exception:
    return False

# CliRuntime.version() line 68:
except Exception:
    return ""

# CliRuntime.info() line 96:
except Exception:
    return {}

# CliRuntime.ping() line 104:
except Exception:
    return False
```

**Problem:** `except Exception` catches `MemoryError`, `AssertionError`, `TypeError`, `ValueError`, and any other unexpected `Exception` subclass — silently returning `False`/`""`/`{}` instead of propagating. The `transport/cli.py:159` site was already removed by Finding #7 (execute_pty elimination).

**Correction to original audit:** The original report claimed `except Exception` catches `KeyboardInterrupt` and `SystemExit`. In standard Python, `KeyboardInterrupt` and `SystemExit` inherit from `BaseException`, not `Exception` — `except Exception` never catches them. They always propagate even with the buggy code. The real risk is `MemoryError`, `AssertionError`, and unexpected programming errors being silently swallowed.

**Fix:** Narrow to specific exceptions that `CliTransport.execute()` can realistically raise: `RuntimeNotAvailableError` (binary not found), `subprocess.TimeoutExpired` (command timeout), `OSError` (OS-level failures).

### Proposed Solution

#### Approach: Narrow `except Exception` to `except (RuntimeNotAvailableError, subprocess.TimeoutExpired, OSError)`

Replace `except Exception` with a tuple of the three expected exception types in all 4 sites in `engine/cli.py`. This is a one-line change per site — no structural changes, no new imports needed (`RuntimeNotAvailableError` is already imported via `domain.exceptions`).

**Update** `adapters/engine/cli.py` — 2 import additions + 4 exception tuple replacements.

**📦 Imports to add** (follow alphabetical grouping):

```python
import subprocess                                          # new
from typing import Any

from oci_runtime.domain.exceptions import (                 # new — RuntimeNotAvailableError added
    RuntimeNotAvailableError,
)
from oci_runtime.ports.capabilities import RuntimeCapabilities
```

**Notes:**
- `import subprocess` needed for `subprocess.TimeoutExpired` in the exception tuple
- `RuntimeNotAvailableError` imported from domain — same pattern as `transport/cli.py:6`
- `OSError` is a built-in — no import needed
- Transports that raise `FileNotFoundError` convert it to `RuntimeNotAvailableError` internally — never reaches engine handler

**🔁 4 exception tuple replacements:**

| Method | Line | Current | Fixed |
|---|---|---|---|
| `is_available()` | 57 | `except Exception:` | `except (RuntimeNotAvailableError, subprocess.TimeoutExpired, OSError):` |
| `version()` | 68 | `except Exception:` | Same |
| `info()` | 96 | `except Exception:` | Same |
| `ping()` | 104 | `except Exception:` | Same |

**Verification — CliTransport.execute() can raise these 3 exceptions only:**

| Exception | Raised by? | Caught? |
|---|---|---|
| `RuntimeNotAvailableError` | `_ensure_binary()` + `except FileNotFoundError` | ✅ Yes — engine unavailable |
| `subprocess.TimeoutExpired` | `process.wait(timeout=...)` (both streaming + non-streaming) | ✅ Yes — command timeout |
| `OSError` | Subprocess internals (permission, path, etc.) | ✅ Yes — system failure |
| `FileNotFoundError` | Converted to RuntimeNotAvailableError before reaching engine | ❌ Never reaches handler |
| `ContainerRuntimeError` | PTY utility only, not `execute()` | ❌ Not in scope |
| `MemoryError` | Anywhere | ❌ Let it propagate |
| `AssertionError` | Programming error | ❌ Let it propagate |

**No other changes needed** — `__init__` signature unchanged, `info()` inner `try/except json.JSONDecodeError` (lines 84-87) unaffected, all return types preserved.

#### Tests to Add/Update

**`tests/unit/adapters/test_cli_runtime.py`** (file exists, 3 existing tests, 68 lines).

**📦 Imports to add** (3 additions):

```python
import subprocess                                          # new — for subprocess.TimeoutExpired
import pytest                                              # new — for pytest.raises()
from unittest.mock import MagicMock

from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.domain.exceptions import (                 # new — RuntimeNotAvailableError added
    RuntimeNotAvailableError,
)
from oci_runtime.ports.capabilities import RuntimeCapabilities
...
```

**⚠️ Existing test `test_is_available_false_when_transport_raises` (lines 50-61) will break** — it raises a generic `Exception`, but the narrowed handler `except (RuntimeNotAvailableError, subprocess.TimeoutExpired, OSError)` does not catch it. The exception propagates uncaught and the `assert` on line 61 is never reached.

**🔁 Action:** Rename it to `test_is_available_propagates_unexpected_exception` and flip the assertion to `pytest.raises(Exception)`.

**Constructor boilerplate note:** Every test creates a `CliRuntime` with all 5 manager `MagicMock` args even though `is_available()`/`version()`/`info()`/`ping()` don't use managers. This is an existing pattern (see lines 40-47, 53-60). Keep repeating it — don't extract a fixture or helper. Consistency with existing code.

**`_mock_transport` helper** (lines 64-68) sets `return_value` only. Propagation tests need `side_effect` instead. Use the inline pattern from lines 51-52: create `MagicMock(spec=Transport)` directly and set `side_effect`. Don't modify the helper.

**Full test table:**

| Action | Test name | Pattern |
|---|---|---|
| 🔄 **Rename existing** (was `test_is_available_false_when_transport_raises`) | `test_is_available_propagates_unexpected_exception` | `side_effect = Exception("binary not found")` → `pytest.raises(Exception)` |
| ➕ **New** | `test_is_available_propagates_memory_error` | `side_effect = MemoryError("oom")` → `pytest.raises(MemoryError)` |
| ➕ **New** | `test_version_propagates_assertion_error` | `side_effect = AssertionError("bug")` → `pytest.raises(AssertionError)` |
| ➕ **New** | `test_is_available_still_catches_runtime_not_available` | `side_effect = RuntimeNotAvailableError("docker")` → `assert runtime.is_available() is False` |
| ➕ **New** | `test_is_available_still_catches_timeout_expired` | `side_effect = subprocess.TimeoutExpired("docker --version", timeout=30)` → `assert runtime.is_available() is False` |
| ➕ **New** | `test_version_still_catches_runtime_not_available` | `side_effect = RuntimeNotAvailableError("docker")` → `assert runtime.version() == ""` |
| ➕ **New** | `test_info_still_catches_os_error` | `side_effect = OSError("permission denied")` → `assert runtime.info() == {}` |
| ➕ **New** | `test_ping_still_catches_os_error` | `side_effect = OSError("permission denied")` → `assert runtime.ping() is False` |

**An `is_available` propagation test (MemoryError), written in final form:**

```python
def test_is_available_propagates_memory_error(self):
    transport = MagicMock(spec=Transport)
    transport.execute.side_effect = MemoryError("oom")
    runtime = CliRuntime(
        transport=transport,
        image_manager=MagicMock(spec=ImageManager),
        container_manager=MagicMock(spec=ContainerManager),
        volume_manager=MagicMock(spec=VolumeManager),
        network_manager=MagicMock(spec=NetworkManager),
        caps=RuntimeCapabilities(),
    )
    with pytest.raises(MemoryError):
        runtime.is_available()
```

All other propagation tests follow the same 8-line body template (swap exception type + method). All catch tests swap `pytest.raises(...)` for `assert ... is False` / `== ""` / `== {}`.

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|---|---|---|
| Domain: pure Python, no I/O | ✅ Unchanged | No domain types modified |
| Ports: ABCs only, no implementation | ✅ Unchanged | `ContainerEngine` ABC signatures preserved |
| Adapters: implement contracts, contain I/O | ✅ | `CliRuntime` (adapter) — exception narrowing is adapter concern |
| Adapters: no business logic | ✅ | Exception handling only — no domain logic |
| Factory: only DI composition root | ✅ Unchanged | No factory wiring changes |
| Backward compatible | ✅ | Expected exceptions caught identically. Fatal exceptions now propagate — caller decides |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-06-02
**Changes applied:**

1. **`adapters/engine/cli.py`** — Added `import subprocess` and `RuntimeNotAvailableError` import from `domain.exceptions`. Replaced `except Exception:` with `except (RuntimeNotAvailableError, subprocess.TimeoutExpired, OSError):` in all 4 methods (`is_available()`, `version()`, `info()`, `ping()`).
2. **`tests/unit/adapters/test_cli_runtime.py`** — Expanded from 3 to 10 tests: renamed `test_is_available_false_when_transport_raises` to `test_is_available_propagates_unexpected_exception` with `pytest.raises(Exception)` assertion. Added 7 new tests covering propagation of fatal errors (`MemoryError`, `AssertionError`) and correct catching of expected exceptions (`RuntimeNotAvailableError`, `subprocess.TimeoutExpired`, `OSError`).
3. **`tests/integration/integration/test_engine_lifecycle.py`** — Updated 4 integration tests from generic `Exception` to `OSError` to match the narrowed exception handlers (same error-path semantics preserved).

**Solution rationale:** Narrowed `except Exception` across all 4 `CliRuntime` methods to `except (RuntimeNotAvailableError, subprocess.TimeoutExpired, OSError)`. Fatal errors (`MemoryError`, `AssertionError`, programming bugs) now propagate instead of being silently swallowed. Expected transport failures continue to be caught gracefully with the same return values (`False`, `""`, `{}`). The three exceptions mirror exactly what `CliTransport.execute()` can realistically raise — any other `Exception` subclass is a programming error that should not be hidden from callers.

**Verification:** 635 tests pass (0 failures) across unit and integration suites.

---

### Finding #16: `selector.select(timeout=0.1)` Suboptimal + stdin Deadlock

**File:** `adapters/transport/cli.py:61-63,76-77`

**Two separate issues:**

**Issue A — The select timeout spin loop (line 76-77):**
```python
while process.poll() is None or selector.get_map():
    events = selector.select(timeout=0.1)
```

This is **NOT a busy-wait**. `select()` with a timeout is a blocking syscall — the kernel suspends the thread for up to 100ms. At idle, this produces ~10 context switches/second, consuming ~0.01-0.05% CPU. This is negligible.

**The REAL problem with this loop:** When pipes hit EOF and are unregistered from the selector, but the process is still alive:
- `selector.get_map()` returns `{}` (empty)
- `process.poll()` returns `None` (still running)
- `while None or {}` → `while True or False` → `while True` → infinite spin
- `select()` with an empty epoll instance returns **IMMEDIATELY** (no fds to monitor)
- This is a **true 100% CPU busy-wait** until the process finally exits

This edge case is rare (pipes usually close when the process exits), but when it triggers, CPU spikes to 100%.

**Issue B — stdin deadlock (lines 61-63):**
```python
if input_data:
    process.stdin.write(input_data)   # blocks on write
    process.stdin.close()
```

**This is a critical deadlock bug in the streaming path.** On Linux, pipe buffers default to 64KB. If `input_data` is larger than PIPE_BUF (e.g., a 10MB tar for `docker build -`):

1. `write()` fills the 64KB pipe buffer, then **blocks**
2. The child process can't read stdin yet — it first writes output (e.g., build progress)
3. The child's stdout fills its 64KB buffer — child **blocks** on write
4. Parent is blocked on `write(input_data)`, child is blocked on `write()` — **DEADLOCK**

**The non-streaming path (`subprocess.run`) handles this correctly internally** by using a thread to write stdin concurrently with reading output. The streaming path does not.

### Proposed Solution

#### Approach: Option A — Targeted fixes (daemon thread for stdin + process.wait guard for spin)

**Fix 16a — CPU spin:** Replace the raw `while process.poll() is None or selector.get_map()` condition with an explicit three-way guard that breaks when both conditions are met, uses `process.wait(timeout=0.1)` as a blocking sleep when pipes are drained but the process is alive, and falls through to `selector.select()` normally when pipes still have data:

```python
while True:
    if process.poll() is not None and not selector.get_map():
        break
    if not selector.get_map():
        process.wait(timeout=0.1)
        continue
    events = selector.select(timeout=0.1)
    ...
```

Rather than spinning on `selector.select()` with an empty epoll instance (which returns immediately — 100% CPU), the fix calls `process.wait(timeout=0.1)` which is a blocking syscall — the kernel suspends the thread for up to 100ms. This consumes ~0% CPU and is functionally equivalent: the thread wakes at most every 100ms to check if the process has exited.

**Fix 16b — stdin deadlock:** Write stdin in a daemon thread so the main thread can enter the read loop concurrently:

```python
_stdin_thread = None
if input_data:
    def _write_stdin():
        process.stdin.write(input_data)
        process.stdin.close()
    _stdin_thread = threading.Thread(target=_write_stdin, daemon=True)
    _stdin_thread.start()
```

The main thread reads stdout/stderr in the selector loop. If the child produces output, the pipes drain, the child can make progress on reading stdin, and the deadlock is broken. The stdin thread remains blocked in the background if the pipe never drains — as a daemon thread, it's cleaned up on interpreter exit.

After the read loop, a `_stdin_thread.join(timeout=5)` ensures the write completed (or times out gracefully).

**Architectural rationale:** The two bugs use different I/O patterns because stdin is a **push** (one producer: the parent) while stdout/stderr are **pull** (two producers: the child). A daemon thread is the correct tool for the blocking push. Selectors are the correct tool for the multi-source pull. Using one mechanism for both (threads for everything, or selectors for everything) would either over-engineer the write side or under-serve the read side.

**Update** `adapters/transport/cli.py`:
- Add `import threading` to top of file
- Lines 61-63: Replace `process.stdin.write(input_data)` + `process.stdin.close()` with daemon thread pattern
- Lines 76-91: Replace `while process.poll() is None or selector.get_map():` with guarded three-way loop
- After `selector.close()` block: Add `_stdin_thread.join(timeout=5)` before `process.wait()`

#### Tests to Add/Update

**`tests/unit/adapters/test_cli_transport.py`** — New tests:
- `test_streaming_no_spin_on_empty_selector_map`: Mock Popen where pipes close before process exits — verify CPU doesn't spin
- `test_streaming_stdin_in_daemon_thread`: Verify stdin is written in a thread, not the main thread
- `test_streaming_large_input_no_deadlock`: Verify >64KB input doesn't deadlock the streaming path
- `test_streaming_normal_case_unaffected`: Verify normal streaming still returns correct data
- `test_streaming_on_output_still_works`: Verify callbacks still fire

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|---|---|---|
| Domain: pure Python, no I/O | ✅ Unchanged | No domain types modified |
| Ports: ABCs only, no implementation | ✅ Unchanged | `Transport.execute()` signature unchanged — `stream`, `on_output`, `input_data` all preserved |
| Ports: `ExecResult` return type | ✅ Unchanged | `ExecResult(returncode: int, stdout: bytes, stderr: bytes)` unchanged |
| Adapters: implement contracts, contain I/O | ✅ | `threading` and `selectors` stay in `CliTransport` — adapter layer only |
| Adapters: orchestration only, no business logic | ✅ | Write input → read output → wait for exit — no domain logic added |
| Factory: only DI composition root | ✅ Unchanged | `Transport` ABC unchanged, no factory wiring changes |
| Streaming semantics preserved | ✅ | `stream=True` still streams, `on_output` callback still fires, returns `ExecResult` |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-06-01
**Changes applied:**

1. **`adapters/transport/cli.py`** — Added `import threading`. Applied two fixes:
   - **Fix 16a (CPU spin):** Replaced `while process.poll() is None or selector.get_map()` with a three-way guard that breaks when both process exited and pipes drained, calls `process.wait(timeout=0.1)` when pipes are empty but process is alive (blocking syscall, ~0% CPU), and falls through to `selector.select()` normally when pipes have data.
   - **Fix 16b (stdin deadlock):** Replaced blocking `process.stdin.write(input_data)` with a daemon thread pattern (`threading.Thread(target=_write_stdin, daemon=True).start()`) so the main thread enters the read loop concurrently, preventing deadlock when input_data exceeds Linux PIPE_BUF (64KB). Added `_stdin_thread.join(timeout=5)` after the selector loop.
2. **`tests/unit/adapters/test_cli_transport.py`** — Added 5 new tests: `test_streaming_no_spin_on_empty_selector_map`, `test_streaming_stdin_in_daemon_thread`, `test_streaming_large_input_no_deadlock`, `test_streaming_normal_case_unaffected`, `test_streaming_on_output_still_works`.

**Verification:** 628/628 tests pass (0 failures). All 5 new tests pass.

**Solution rationale:** The two bugs used different I/O patterns requiring different mechanisms — stdin is a blocking push (daemon thread), stdout/stderr are a multi-source pull (selectors). Using a daemon thread for stdin write prevents the >64KB deadlock by allowing the main thread to drain stdout/stderr concurrently. The three-way guard on the selector loop prevents 100% CPU spin when pipes close before the process exits by calling `process.wait(timeout=0.1)` instead of `selector.select()` on an empty epoll instance. Both fixes are confined to the adapter layer — no port, domain, or factory changes needed.

---

### Finding #17: Unit Tests Don't Assert `create()` Return Values

**Files:** `tests/unit/adapters/test_cli_volume_manager.py`, `test_cli_network_manager.py`

**Code (original, before Finding #1 fix):**
```python
def test_create_calls_transport(self):
    self.manager.create("my-vol")
    self.transport.execute.assert_called_once()  # Doesn't check return value
```

**Problem:** Originally, no test asserted the return value of `create()` methods. This is how Finding #1 (bytes vs str type violation) went undetected. The return value was silently assumed to be correct.

**Current state:** The Finding #1 fix added `test_create_returns_str` in both files, asserting the return value is a `str` and matches the expected name. The core gap is closed.

**Remaining gap:** `test_create_calls_transport` still only checks `execute` was called once — it doesn't verify the CLI command was constructed correctly. If the command ordering or flags change (e.g., `--driver` before vs after `name`, missing `--label` args), the test won't catch it.

### Proposed Solution

#### Approach: Expand `test_create_calls_transport` to verify command + add driver/label variants + fix mock port vs impl confusion

Replace `self.transport.binary = "docker"` (vestigial attribute, nobody reads it) with `self.transport.get_runtime_binary.return_value = "docker"` (port contract method). Decouple create arg from mock stdout in volume tests to make the decode pipeline explicit. Replace `assert_called_once()` with `assert_called_once_with([...])`. Add two new tests for custom driver and label variants.

**Update** `tests/unit/adapters/test_cli_volume_manager.py`:

In `setup_method`, replace the vestigial `binary` attribute with the port method mock, and decouple mock stdout from the create arg:
```python
# Remove: self.transport.binary = "docker"  (vestigial — nobody reads it)
# Add:
self.transport.get_runtime_binary.return_value = "docker"
self.transport.execute.return_value = ExecResult(returncode=0, stdout=b"test-volume", stderr=b"")
```

Update `test_create_returns_str` to assert the decoded stdout (not coincidental arg equality):
```python
def test_create_returns_str(self):
    name = self.manager.create("my-vol")
    assert isinstance(name, str)
    assert name == "test-volume"       # checks decode pipeline, not arg identity
```

Rename `test_create_calls_transport` and replace the body:
```python
def test_create_calls_transport_with_correct_command(self):
    self.manager.create("my-vol")
    self.transport.execute.assert_called_once_with(
        ["docker", "volume", "create", "--driver", "local", "my-vol"]
    )
```

Add two new tests:
```python
def test_create_calls_transport_with_custom_driver(self):
    self.manager.create("my-vol", driver="nfs")
    self.transport.execute.assert_called_once_with(
        ["docker", "volume", "create", "--driver", "nfs", "my-vol"]
    )

def test_create_calls_transport_with_labels(self):
    self.manager.create("my-vol", labels={"env": "test", "project": "foo"})
    self.transport.execute.assert_called_once_with(
        ["docker", "volume", "create", "--driver", "local", "my-vol",
         "--label", "env=test", "--label", "project=foo"]
    )
```

**Update** `tests/unit/adapters/test_cli_network_manager.py`:

Same structural changes — replace `binary` attribute with `get_runtime_binary.return_value`, decouple mock stdout from create arg:
```python
# In setup_method:
self.transport.get_runtime_binary.return_value = "docker"
self.transport.execute.return_value = ExecResult(returncode=0, stdout=b"test-network", stderr=b"")

# test_create_returns_str now asserts mock stdout, not arg:
def test_create_returns_str(self):
    name = self.manager.create("my-net")
    assert isinstance(name, str)
    assert name == "test-network"     # same pattern as volume
```

Replace `test_create_calls_transport` with command verification + add driver/label variants (same pattern as volume, with network-specific commands).

#### Tests Added/Updated

| File | Change |
|------|--------|
| `test_cli_volume_manager.py` | `setup_method` — removed vestigial `binary` attribute, added `get_runtime_binary.return_value`, decoupled mock stdout from create arg (`b"test-volume"`) |
| `test_cli_volume_manager.py` | `test_create_returns_str` — assertion changed from `"my-vol"` to `"test-volume"` (tests decode pipeline, not arg coincidence) |
| `test_cli_volume_manager.py` | `test_create_calls_transport` → renamed to `test_create_calls_transport_with_correct_command`, body uses `assert_called_once_with` |
| `test_cli_volume_manager.py` | Added `test_create_calls_transport_with_custom_driver` |
| `test_cli_volume_manager.py` | Added `test_create_calls_transport_with_labels` |
| `test_cli_network_manager.py` | `setup_method` — same mock cleanup: `binary` → `get_runtime_binary.return_value`, mock stdout to `b"test-network"` |
| `test_cli_network_manager.py` | `test_create_returns_str` — assertion changed from `"net1"` to `"test-network"` (consistent with volume) |
| `test_cli_network_manager.py` | `test_create_calls_transport` → renamed to command-verifying version |
| `test_cli_network_manager.py` | Added `test_create_calls_transport_with_custom_driver` |
| `test_cli_network_manager.py` | Added `test_create_calls_transport_with_labels` |

**Total:** 10 test modifications (2 removals, 2 fixups, 4 renames + 4 new).

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Domain: pure Python, no I/O | ✅ Unchanged | No domain types modified |
| Ports: ABCs only, no implementation | ✅ Unchanged | Port contracts unchanged |
| Ports: tests mock port contract, not impl detail | ✅ Improved | `get_runtime_binary.return_value` replaces `binary="docker"` (was mocking an adapter attribute, not the port method) |
| Adapters: implement contracts, contain I/O | ✅ Unchanged | Production code untouched |
| Factory: only DI composition root | ✅ Unchanged | No factory changes |
| Production code | ✅ Unchanged | Zero production files touched |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-06-02
**Changes applied:**

1. **`tests/unit/adapters/test_cli_volume_manager.py`** — `setup_method`: replaced vestigial `self.transport.binary = "docker"` with `self.transport.get_runtime_binary.return_value = "docker"` (port contract method); decoupled mock stdout from create arg (`b"test-volume"` instead of `b"my-vol"`). `test_create_calls_transport` → renamed to `test_create_calls_transport_with_correct_command` using `assert_called_once_with(["docker", "volume", "create", "--driver", "local", "my-vol"])`. Added `test_create_calls_transport_with_custom_driver` (nfs driver) and `test_create_calls_transport_with_labels` (env/project labels).
2. **`tests/unit/adapters/test_cli_network_manager.py`** — Same structural changes: `binary` → `get_runtime_binary.return_value`, mock stdout to `b"test-network"`, renamed create transport test with `assert_called_once_with`, added driver and label variants.

**Solution rationale:** Replaced the vestigial `binary="docker"` attribute (which was never read by any production code) with the port contract method `get_runtime_binary.return_value="docker"`, fixing a mock-what-you-use violation. Decoupled mock stdout values from create args to make the decode pipeline explicit — `test_create_returns_str` now asserts `"test-volume"` / `"test-network"` instead of coinciding with the input arg. Replaced uninformative `assert_called_once()` with `assert_called_once_with([fully qualified command])` so that command ordering, flags, and arguments are explicitly verified. Added driver and label variants to cover the full surface area of the `create()` signature.

**Verification:** 645 tests pass (0 failures) across unit and integration suites.

---

### Finding #23: `ContainerEngine.info()` Returns Opaque `dict[str, Any]`

**File:** `ports/engine.py:41`

**Code:**
```python
class ContainerEngine(ABC):
    @abstractmethod
    def info(self) -> dict[str, Any]: ...
```

**Problem:** Returns a fully dynamic `dict[str, Any]` with no type safety. The schema differs per runtime — `docker info --format json` returns `{"Containers": 5, "ServerVersion": "24.0", ...}` while `podman info --format json` returns a completely different nested structure `{"host": {...}, "version": {...}, "store": {...}}`. Creating a typed `EngineInfo` dataclass is difficult because the "common fields" are an ever-growing set that must be maintained across runtime versions.

**Investigation:** A full source tree search confirmed **zero production callers** of `.info()` in `src/`. Only test files call it. The use cases it might serve (daemon health check, version info) are already covered by `is_available()` (binary exists + responds) and `version()` (returns version string).

---

### Prototype Validation

**File:** `dev/validation/oci_runtime/finding-23-remove-info.py`

Validates that removing `info()` from the `ContainerEngine` ABC is safe — all test doubles still function, `is_available()` and `version()` cover the same concerns.

#### Prototype Results

```
─── 1. ABC works without info() ───
  PASS | ContainerEngine cannot be instantiated (ABC)
  PASS | ContainerEngine has 2 abstract methods: is_available, version
  PASS | info not in abstract methods

─── 2. CliRuntime works without info() ───
  PASS | is_available() returns True
  PASS | version() returns '24.0.7'
  PASS | No hasattr info on CliRuntime

─── 3. MockEngine works without info() ───
  PASS | MockEngine is_available()
  PASS | MockEngine version()
  PASS | MockEngine has no info attribute

─── 5. Use case coverage ───
  PASS | Binary availability: is_available()
  PASS | Version info: version()
  PASS | System info: removed (zero callers)
  PASS | Health check: is_available() covers it

RESULTS: 15 PASSED, 0 FAILED
```

---

### Proposed Solution

#### Approach: Remove `info()` entirely — dead code elimination

Same pattern as Finding #18 (`ping()` removal). Zero production callers, Docker and Podman have incompatible info schemas, and `is_available()` + `version()` already cover health-check use cases.

**Remove** `ports/engine.py:41` — Delete `info()` abstract method from `ContainerEngine` ABC.

**Remove** `adapters/engine/cli.py:73-99` — Delete `info()` implementation (28 lines including `import json` at line 85, which was only used here).

#### Files to Touch

**2 production files, 7 test files:**

| File | Change |
|------|--------|
| `ports/engine.py` | Remove `def info(self) -> dict[str, Any]: ...` (line 41) |
| `adapters/engine/cli.py` | Remove `info()` method (lines 73-99) + unused `import json` |
| `tests/unit/ports/test_engine.py` | Remove `test_info_is_abstract` (lines 44-45) |
| `tests/unit/adapters/test_cli_runtime.py` | Remove `test_info_still_catches_os_error` (line 146) |
| `tests/integration/integration/test_engine_lifecycle.py` | Remove `TestEngineInfo` class (lines 97-113, 2 tests) |
| `tests/integration/capability/test_capabilities.py` | Remove 2 info tests (lines 35-50) |
| `tests/integration/smoke/test_real_runtime.py` | Remove `test_live_engine_info_returns_dict` (lines 28-31) |
| `tests/integration/contract/test_interface_compliance.py` | Remove `"info"` from `expected_methods` set (line 118). Remove `assert callable(runtime.info)`. |
| `tests/integration/integration/test_factory_wiring.py` | Remove `def info(self): return {}` from `MockEngine` (line 117) |

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Domain: pure Python, no I/O | ✅ Unchanged | No domain types touched |
| Ports: ABCs only, no implementation | ✅ | Removing a broken abstraction — `info()` had no universal type contract across runtimes |
| Adapters: implement contracts, contain I/O | ✅ | Removing adapter code that parsed runtime-specific JSON into a generic dict |
| Factory: only DI composition root | ✅ Unchanged | No factory changes needed |
| Coverage: `is_available()` + `version()` fill the gap | ✅ | Binary check + version string cover the same concerns |

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-06-11
**Changes applied:**

1. **`ports/engine.py`** — Removed `info()` abstract method from `ContainerEngine` ABC (line 40-41) + unused `from typing import Any`
2. **`adapters/engine/cli.py`** — Removed `info()` implementation from `CliRuntime` (lines 73-99) + unused `from typing import Any`
3. **`tests/unit/ports/test_engine.py`** — Removed `test_info_is_abstract`
4. **`tests/unit/adapters/test_cli_runtime.py`** — Removed `test_info_still_catches_os_error`
5. **`tests/integration/integration/test_engine_lifecycle.py`** — Removed entire `TestEngineInfo` class (2 tests)
6. **`tests/integration/capability/test_capabilities.py`** — Removed 2 info tests
7. **`tests/integration/smoke/test_real_runtime.py`** — Removed `test_live_engine_info_returns_dict`
8. **`tests/integration/contract/test_interface_compliance.py`** — Removed `"info"` from `expected_methods` set and `assert callable(runtime.info)`
9. **`tests/integration/integration/test_factory_wiring.py`** — Removed `def info(self): return {}` from `MockEngine`

**Solution rationale:** `info()` is never called by any production code. Docker and Podman have incompatible info schemas (`docker info --format json` returns flat key-value while `podman info --format json` returns deeply nested structure), making a typed `EngineInfo` dataclass effectively impossible to maintain. `is_available()` (binary exists + `--version` responds) and `version()` (returns version string) already cover the health-check and system-info use cases correctly. Removing `info()` from the port layer is architecturally correct — it acknowledges that the abstraction was not universally realizable with a single return type.

**Verification:** 645 tests pass (0 failures) across unit and integration suites.

---

### Finding #24: Domain Type Inconsistencies

**Files:** `domain/enums.py:4`, `domain/types.py:21,25-26`

Three sub-issues were investigated. Two were determined to be architecturally acceptable as-is; one requires a fix.

---

#### Sub-Issue A: `RuntimeKind` Uses `Enum` Not `StrEnum`

**Investigation:** The majority pattern across the production codebase is `Enum` (16 of 26 enums). `StrEnum` is the minority (9 of 26). The sibling `container-manager` module uses `Enum` exclusively — zero `StrEnum`. Within `oci-runtime/domain/enums.py`, `RuntimeKind` is consistent with `RestartPolicy` and `NetworkMode` (all `Enum`); only `ContainerState` uses `StrEnum`.

**Resolution:** The pattern is not incorrect. `RuntimeKind` as `Enum` follows the majority pattern across the codebase. No change needed.

---

#### Sub-Issue B: `BuildContext.build_file` Has Dual Path/Content Semantics

**File:** `domain/types.py:25-26`

**Code:**
```python
@dataclass
class BuildContext:
    build_file: str | Path
    context_path: Path | None = None
    files: dict[str, bytes] = field(default_factory=dict)
```

**Problem:** The `build_file` field serves double duty:
- `str` — inline Dockerfile content
- `Path` — filesystem path to an existing Dockerfile

The adapter uses `isinstance(context.build_file, Path)` to guess which meaning the caller intended. Domain types should have unambiguous semantics — a field changing meaning based on `isinstance` is a design smell.

**Root cause:** The union type `str | Path` conflates two semantically distinct values (content vs location) into one field, pushing the disambiguation responsibility to the adapter via runtime type inspection.

**Investigation — caller patterns:**
- **`build_file="FROM alpine"` (str):** 18 sites — the dominant case, used in tests and integration
- **`build_file=Path("/some/Dockerfile")` (Path):** 4 sites — 2 in tests, 2 in CLI consumer tools

The sibling `container-manager` module has the exact same issue with a field named `dockerfile: str | Path` and the same three-branch `isinstance` pattern.

---

### Prototype Validation

**File:** `dev/validation/oci_runtime/finding-24-buildcontext-split.py`

A standalone Python script validates the approach end-to-end with 32 tests covering construction validation (both set, neither set, individual fields), all three adapter branches, caller migration patterns, and edge cases.

#### Prototype Results

```
─── 1. Construction validation (post_init) ───
  PASS | build_file_content set, build_file_path is None
  PASS | build_file_content is 'FROM alpine'
  PASS | build_file_path set, build_file_content is None
  PASS | build_file_path is /tmp/Dockerfile
  PASS | Both set raises ValueError
  PASS | Neither set raises ValueError

─── 2. Adapter: build_file_path branch ───
  PASS | Path only: cmd has -f <path>
  PASS | Path only: context is parent dir
  PASS | Path + context_path: context is context_path

─── 3. Adapter: build_file_content + context_path branch ───
  PASS | cmd has -f -, context_path in cmd
  PASS | input_data is encoded Dockerfile content

─── 4. Adapter: build_file_content only (tar) ───
  PASS | cmd has - for stdin, tar is valid
  PASS | tar contains Dockerfile + extra files

─── 5. Caller pattern equivalency ───
  PASS | str→build_file_content, Path→build_file_path
  PASS | str+ctx→build_file_content+context_path

─── 6. Edge cases ───
  PASS | Full content build with all fields works
  PASS | Both set raises ValueError, neither set raises ValueError

RESULTS: 32 PASSED, 0 FAILED
```

---

### Proposed Solution

#### Approach: Split `build_file` into explicit fields with `__post_init__` validation

Replace the single `build_file: str | Path` with two mutually exclusive explicit fields. A `__post_init__` hook enforces that exactly one is set, catching mistakes at construction time (where they belong) rather than at adapter dispatch time.

**Update** `domain/types.py`:
```python
@dataclass
class BuildContext:
    """Build context for container image builds.

    Exactly one of build_file_content or build_file_path must be set.
    """

    build_file_content: str | None = None
    build_file_path: Path | None = None

    context_path: Path | None = None
    files: dict[str, bytes] = field(default_factory=dict)
    build_args: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    target: str | None = None
    network: str | None = None
    no_cache: bool = False
    pull: bool = False
    rm: bool = True
    build_contexts: dict[str, str | Path] = field(default_factory=dict)

    def __post_init__(self):
        has_content = self.build_file_content is not None
        has_path = self.build_file_path is not None
        if has_content and has_path:
            raise ValueError(
                "BuildContext: cannot set both build_file_content and "
                "build_file_path. Use build_file_content for inline "
                "Dockerfile text or build_file_path for a path."
            )
        if not has_content and not has_path:
            raise ValueError(
                "BuildContext: must set either build_file_content or "
                "build_file_path."
            )
```

**Update** `adapters/managers/image.py` — replace `isinstance` branches with explicit field checks:
```python
# Branch 1: explicit file path on disk
if context.build_file_path is not None:
    cmd.extend(["-f", str(context.build_file_path)])
    cmd.append(str(context.context_path or context.build_file_path.parent))

# Branch 2: inline content + context directory → stdin
elif context.context_path is not None:
    cmd.extend(["-f", "-"])
    cmd.append(str(context.context_path))
    input_data = context.build_file_content.encode("utf-8")

# Branch 3: inline content only → in-memory tar
elif context.build_file_content is not None:
    input_data = _create_tar(
        context.build_file_content, context.files, self._caps.tar_entry_name
    )
    cmd.append("-")
```

**Branch ordering rationale:** Branch 1 checks `build_file_path` first — if the caller provided an explicit file path, that always takes priority. Branch 2 checks `context_path` next — this distinguishes "content + directory" (stdin pipe) from "content only" (tar). Branch 3 is the fallback — `__post_init__` guarantees `build_file_content` is set if we reach here, so the `elif` is a defensive guard.

The chain is: **explicit file path > mixed mode (content + dir) > pure content (tar).**

#### Files to Touch

**2 production files:**

| File | Change |
|------|--------|
| `domain/types.py` | Replace `build_file: str \| Path` with `build_file_content: str \| None = None` and `build_file_path: Path \| None = None`. Add `__post_init__` with mutual exclusivity validation. |
| `adapters/managers/image.py` | Replace `isinstance(context.build_file, Path)` branches with `context.build_file_path is not None` / `context.build_file_content is not None`. Remove old `isinstance` import. |

**All caller sites — precise enumeration (10 test files, 16 construction sites):**

| File | Line | Current | New |
|------|------|---------|-----|
| `tests/unit/domain/test_types.py` | 75 | `build_file="FROM alpine"` | `build_file_content=` |
| same | 79 | `build_file=Path("/some/Containerfile")` | `build_file_path=` |
| same | 83 | `build_file="FROM alpine"` | `build_file_content=` |
| same | 96-98 | `build_file=Path("Containerfile")` | `build_file_path=` |
| `tests/unit/adapters/test_cli_image_manager.py` | 45 | `build_file="FROM alpine"` | `build_file_content=` |
| same | 54 | `build_file="FROM alpine:latest", context_path=..` | `build_file_content=` |
| same | 60 | `build_file="FROM alpine", context_path=..` | `build_file_content=` |
| same | 69 | `build_file="FROM alpine"` | `build_file_content=` |
| `tests/unit/ports/test_image_manager_contract.py` | 37 | `build_file="FROM alpine"` | `build_file_content=` |
| same | 99 | `build_file="FROM alpine"` | `build_file_content=` |
| `tests/integration/functional/test_workflows.py` | 72 | `build_file="FROM alpine\n..."` | `build_file_content=` |
| same | 84 | `build_file=dfile` (Path) | `build_file_path=` |
| `tests/integration/integration/test_manager_commands.py` | 45 | `build_file="FROM alpine"` | `build_file_content=` |
| `tests/integration/boundary/test_empty_outputs.py` | 106 | `build_file="FROM alpine"` | `build_file_content=` |
| `tests/integration/boundary/test_malformed_output.py` | 100 | `build_file="FROM alpine"` | `build_file_content=` |
| same | 108 | `build_file="FROM alpine"` | `build_file_content=` |

**Assertion sites to update (1 file, 3 sites):**

| File | Line | Current | New |
|------|------|---------|-----|
| `tests/unit/domain/test_types.py` | 76 | `ctx.build_file == "FROM alpine"` | `ctx.build_file_content` |
| same | 80 | `ctx.build_file == Path("/some/Containerfile")` | `ctx.build_file_path` |
| same | 109 | `ctx.build_file == Path("Containerfile")` | `ctx.build_file_path` |

**No changes** needed to port ABCs (`ImageManager.build()` signature unchanged), factory, parsers, or `__init__.py` (name-only re-export — no field references).

#### Sibling Module: `container-manager`

The sibling `container-manager` module has the exact same issue with `BuildContext.dockerfile: str | Path` at `src/shared/container-manager/src/container_manager/core/types.py:45`. This fix should be replicated there in a separate pass with the same pattern: split `dockerfile` into `dockerfile_content: str | None` and `dockerfile_path: Path | None` with `__post_init__` validation, and update its two adapter implementations (`docker/image.py` and `cli/image.py`).

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Domain: pure Python, no I/O | ✅ Unchanged | `__post_init__` is stdlib dataclass feature — no I/O, no adapter imports |
| Domain: unambiguous semantics | ✅ Fixed | `build_file_content` and `build_file_path` are explicit — no `isinstance` guessing |
| Domain: validation at boundary | ✅ Fixed | Mutual exclusivity enforced at construction time, not at dispatch time |
| Ports: ABCs only, no implementation | ✅ Unchanged | `ImageManager.build()` signature unchanged (`context: BuildContext`) |
| Adapters: no `isinstance` on domain types | ✅ Fixed | Adapter checks field identity (`build_file_path is not None`), not type inference |
| Factory: only DI composition root | ✅ Unchanged | No factory changes needed |
| Consistency with container-manager | 📋 Planned | Same pattern should be applied to sibling module's `BuildContext.dockerfile` |

**Status:** PLAN APPROVED
**Date:** 2026-06-03

---

#### Sub-Issue C: `PortMapping.host_ip` Default Is `"127.0.0.1"`

**Investigation:** A full trace of every construction site, parser fallback, and assertion across both oci-runtime and container-manager confirmed:

| Concern | Finding |
|---------|---------|
| Domain default | `"127.0.0.1"` |
| Docker parser fallback | `binding.get("HostIp", "127.0.0.1")` |
| Podman parser fallback | `mapping.get("HostIp", "127.0.0.1")` |
| container-manager parser fallback | `binding.get("HostIp", "127.0.0.1")` |
| container-manager domain default | `"127.0.0.1"` (documented: "localhost for security") |
| Doc consistency | ✅ All 4 parsers agree with domain default |

The domain default and all parser fallbacks already agree. No discrepancy exists. The default is explicitly security-conscious (localhost-only unless overridden). Changing to `"0.0.0.0"` would require updating all 4 parser fallbacks and would silently expose ports to all network interfaces by default — a regression.

**Resolution:** The default is correct and consistent with the parsers. No change needed.

---

### Finding #25: Module-Level Mutable Engine Presets + `RuntimePreference` Contradicts Documented Contract

**File:** `engines.py:4-5`, `ports/capabilities.py:12-23`

**Code:**
```python
# engines.py — mutable module-level singletons
docker_pref = RuntimePreference(kind=RuntimeKind.DOCKER)
podman_pref = RuntimePreference(kind=RuntimeKind.PODMAN)

# ports/capabilities.py — "no guessing" but silently falls back
class RuntimePreference:
    kind: RuntimeKind
    binary: str | None = None

    def get_binary(self) -> str:
        return self.binary if self.binary else self.kind.value
```

**Problems:**

**Issue A — Mutable singletons:** `docker_pref` and `podman_pref` are module-level objects. Any consumer can mutate them:
```python
from oci_runtime import engines
engines.docker_pref.binary = "podman"  # silently changes Docker to Podman binary
```

This is especially dangerous because `RuntimePreference` is NOT frozen — all fields are mutable. The sibling `EngineProfile` class (same file, line 6) IS `@dataclass(frozen=True)`, making this inconsistency glaring.

**Issue B — Contradicts documented contract:** The docstring says:
> *"The user MUST declare their preference. No guessing, no fallback. If the requested engine is not available, creation fails immediately."*

But `get_binary()` silently falls back to `self.kind.value` when `binary` is `None`. The method encodes implicit business logic inside a port data object, which is a hexagonal architecture smell — port dataclasses should be dumb data.

**Issue C — `get_binary()` is a method on a port dataclass:** In hexagonal architecture, derivation logic belongs at the caller (adapter) site, not inside a port data object. Moving the derivation to callers makes the port pure and eliminates the contract contradiction.

---

### Prototype Validation

**File:** `dev/validation/oci_runtime/finding-25-freeze-runtimepreference.py`

A standalone Python script validates the approach end-to-end with 21 tests covering frozen dataclass immutability, required binary field, caller patterns (factory, discovery, engines.py defaults), custom binary paths, edge cases, and the docstring contract.

#### Prototype Architecture

1. `OldRuntimePreference` — simulates current code with mutable dataclass, optional `binary`, `get_binary()` method
2. `RuntimePreference` (new) — frozen dataclass with required `binary: str`, no `get_binary()`
3. Simulated `factory.py`, `discovery/cli.py`, `engines.py` — old vs new caller patterns

#### Prototype Results

```
─── 1. Freeze prevents mutation ───
  PASS | Mutation blocked on frozen dataclass

─── 2. engines.py defaults with explicit binary ───
  PASS | docker_pref.binary == 'docker'
  PASS | podman_pref.binary == 'podman'

─── 3. Custom binary paths ───
  PASS | Custom binary stored
  PASS | Kind preserved

─── 4. Factory usage — preference.binary ───
  PASS | factory.create() gets 'docker'
  PASS | factory.create() gets custom path
  PASS | Old behavior match: get_binary() == .binary for docker
  PASS | Old behavior match: get_binary() == .binary for podman
  PASS | Old behavior match: get_binary() == .binary for custom path

─── 5. Discovery usage ───
  PASS | Discovery returns same binaries
  PASS | Discovery: [docker, podman]

─── 6. Edge cases ───
  PASS | Any binary string accepted
  PASS | Kind mutation blocked
  PASS | Equal preferences compare equal
  PASS | Different binaries are not equal
  PASS | Frozen dataclass is hashable

─── 7. Docstring contract: 'No guessing' ───
  PASS | Missing binary fails at construction: missing required argument
  PASS | Caller always sees explicit binary

RESULTS: 21 PASSED, 0 FAILED
```

#### What the Prototype Validates

| Check | Result | Evidence |
|-------|--------|----------|
| Freeze prevents runtime mutation | ✅ Confirmed | `FrozenInstanceError` raised on attribute assignment |
| `binary` required at construction | ✅ Confirmed | `TypeError` raised when `binary` omitted |
| engines.py defaults work with explicit binary | ✅ Confirmed | `docker`, `podman` binary strings match old `get_binary()` output |
| factory callers: `.binary` replaces `.get_binary()` | ✅ Confirmed | All 3 patterns (docker, podman, custom) return identical values |
| discovery callers: same | ✅ Confirmed | Discovery returns `["docker", "podman"]` in both old and new |
| Frozen dataclass benefits | ✅ Confirmed | Hashable, equality comparison works, immutable |
| Docstring contract enforced | ✅ Confirmed | Missing binary is caught at construction, not deferred to runtime |

---

### Proposed Solution

#### Approach: Freeze `RuntimePreference`, make `binary` required, remove `get_binary()`

`RuntimePreference` becomes a pure frozen dataclass with no methods and no optional fields. This aligns it with its sibling `EngineProfile` (already `frozen=True`). The "no guessing" contract is enforced by the type system — callers must always specify the binary. The derivation logic `binary = self.binary or self.kind.value` moves to each caller site, which is architecturally correct: port data objects are dumb, derivation belongs in adapters.

**Update** `ports/capabilities.py:12-23`:
```python
@dataclass(frozen=True)
class RuntimePreference:
    """Explicit user declaration of what engine to use.

    No guessing, no fallback. The binary must be explicitly declared.
    If the requested engine is not available, creation fails immediately.
    """
    kind: RuntimeKind
    binary: str
```

**Update** `engines.py` — explicit binary at construction:
```python
docker_pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker")
podman_pref = RuntimePreference(kind=RuntimeKind.PODMAN, binary="podman")
```

**Update** `factory.py:124` — field access instead of method call:
```python
# Old: binary = preference.get_binary()
# New:
binary = preference.binary
```

**Update** `adapters/discovery/cli.py:17-18` — explicit binary + field access:
```python
# Old: pref = RuntimePreference(kind=kind); binary = pref.get_binary()
# New:
pref = RuntimePreference(kind=kind, binary=kind.value)
binary = pref.binary
```

#### Files to Touch

**4 production files (6 lines total):**

| File | Change | Lines |
|------|--------|-------|
| `ports/capabilities.py` | `@dataclass`→`frozen=True`, `binary: str` (no `\| None`), remove `get_binary()` | 3 |
| `engines.py` | Add `binary="docker"`/`binary="podman"` to both `RuntimePreference()` calls | 2 |
| `factory.py` | `preference.get_binary()` → `preference.binary` | 1 |
| `adapters/discovery/cli.py` | `RuntimePreference(kind=kind, binary=kind.value)`, `.get_binary()` → `.binary` | 2 |

**12 test files — add `binary=` kwarg where currently omitted:**

| File | Lines | Change |
|------|-------|--------|
| `tests/integration/boundary/test_concurrency.py:20` | Add `binary="docker"` |
| `tests/integration/integration/test_factory_wiring.py:98,124,154` | Add `binary="docker"` to 3 sites |
| `tests/integration/contract/test_interface_compliance.py:396,401,405,439` | Add `binary="docker"`/`"podman"` to 4 sites |
| `tests/integration/capability/test_capabilities.py:22,31` | Add `binary="docker"`/`"podman"` |
| `tests/integration/functional/conftest.py:21` | Add `binary="docker"` |
| `tests/unit/adapters/test_discovery.py:135` | Add `binary="docker"` |

**3 test files — assert `.binary` instead of `.get_binary()`:**

| File | Lines | Change |
|------|-------|--------|
| `tests/unit/adapters/test_engines.py:16,26` | `.get_binary()` → `.binary` |
| `tests/integration/contract/test_interface_compliance.py:402,406,410,414` | `.get_binary()` → `.binary` |
| `tests/integration/capability/test_capabilities.py:28,32` | `.get_binary()` → `.binary` |

**Already passing `binary` — no change (6 sites in 5 files):**
- `tests/integration/boundary/test_error_conditions.py:168,178`
- `tests/integration/integration/test_factory_wiring.py:79,84`
- `tests/integration/contract/test_interface_compliance.py:409,413`
- `tests/integration/capability/test_capabilities.py:27`
- `tests/unit/adapters/test_factory.py:54`

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Domain: pure Python, no I/O | ✅ Unchanged | `RuntimeKind` enum unchanged |
| Ports: ABCs only, no implementation | ✅ Improved | `RuntimePreference` is now pure data — no methods, no derivation logic |
| Ports: data objects have no business logic | ✅ Fixed | `get_binary()` removed — derivation moves to callers (adapters/factory) |
| Ports: concrete types are OK as long as pure | ✅ | Frozen dataclass with required fields — still a valid port type |
| Adapters: derivation belongs here | ✅ | `kind.value` passed explicitly at construction — callers decide |
| Factory: still the DI composition root | ✅ Unchanged | `factory.py` accesses `preference.binary` instead of `preference.get_binary()` |
| Factory: no protocol knowledge | ✅ Unchanged | Factory receives `RuntimePreference`, reads `.binary` field — still abstract |
| OCP: adding a new runtime | ✅ Unchanged | New `RuntimeKind` member + provider class + explicit binary in caller |
| Consistency with `EngineProfile` | ✅ Fixed | Both `@dataclass(frozen=True)` with required fields in same file |

The `get_binary()` method was a hexagonal architecture violation — it encoded business logic ("fall back to `kind.value` if binary is unspecified") inside a port data class. Port data objects should be dumb. The derivation is now explicit at each caller site (`kind.value`, `"docker"`, `"podman"`, or a custom path — all are just strings). The docstring contract "no guessing" is enforced by the type system: `binary: str` is required, not optional.

**Status:** ✅ RESOLVED
**Date:** 2026-06-10
**Changes applied:**

1. **`ports/capabilities.py`** — Made `binary` a required field (`str` instead of `str | None = None`), removed `get_binary()` method. `RuntimePreference` is now a pure frozen dataclass with no methods and no optional fields, matching its sibling `EngineProfile` (already `frozen=True`). The docstring was updated to reflect the "no guessing" contract enforced by the type system.

2. **`engines.py`** — Added `binary="docker"`/`binary="podman"` to the `RuntimePreference()` calls for both defaults.

3. **`factory.py:124`** — Changed `preference.get_binary()` → `preference.binary`.

4. **`adapters/discovery/cli.py:17-18`** — Changed `RuntimePreference(kind=kind)` → `RuntimePreference(kind=kind, binary=kind.value)`, `pref.get_binary()` → `pref.binary`.

5. **Test files (12 files updated):** Added `binary=` kwarg to all `RuntimePreference()` calls that omitted it; changed all `.get_binary()` calls to `.binary`; added `TestRuntimePreference` unit tests verifying `binary` is required, `get_binary()` is absent, and frozen dataclass behavior.

**Solution rationale:** `RuntimePreference.get_binary()` encoded business logic ("fall back to `kind.value` if binary is unspecified") inside a port data class — a hexagonal architecture violation where port dataclasses should be dumb data. Making `binary` required and removing `get_binary()` enforces the documented "no guessing" contract via the type system. Derivation logic (`kind.value` as the default binary) now lives at each caller site (engines.py, factory.py, discovery/cli.py), which is architecturally correct: adapters and the factory compose the data, ports hold it.

**Verification:** 649 tests pass (0 failures) across unit and integration suites.

---

### Finding #26: `ImageManager.build()` Temporary File Leaks on Process Crash

**File:** `adapters/managers/image.py:30-37,51-56`

**Code (current):**
```python
temp_name = f"Dockerfile.tmp.{uuid.uuid4().hex}"
temp_file = context.context_path / temp_name
temp_file.write_text(context.build_file)
cmd.extend(["-f", str(temp_file)])

# ... later in finally:
if temp_file and temp_file.exists():
    try:
        temp_file.unlink()
    except Exception:
        pass  # silently leaks
```

**Problem:** When `context.build_file` is a string and `context.context_path` is set, a temp file is written inside the user's build context directory. Two leak scenarios:

1. **Crash leak:** If the process receives SIGKILL (OOM killer, timeout kill, hard crash) between line 34 (`write_text`) and the `finally` block, the `Dockerfile.tmp.<uuid>` is orphaned in the user's project directory forever.

2. **Silent cleanup failure:** The `except Exception: pass` on line 55 swallows every `unlink()` error (permissions, file lock, stale NFS handle, read-only filesystem). The file stays on disk with zero indication to the caller.

3. **Context directory pollution:** Temp files are created inside the build context directory (the user's project directory), not the system temp directory. A leaked file can accidentally be committed to version control.

**Root cause:** Manual temp file management using UUID-based names written directly into the context directory, with no guard against process death or cleanup failures. The tempfile should either not exist (eliminate the file) or live in the OS temp directory.

---

### Prototype Validation

**File:** `dev/validation/oci_runtime/finding-26-eliminate-temp-file.py`

A standalone Python script validates the approach end-to-end with 17 tests covering the current bug, fixed approach, all three code paths, edge cases, and real Docker/Podman CLI builds.

#### Prototype Architecture

1. `BuggyImageManager` — simulates current code with temp file in context directory
2. `FixedImageManager` — implements fix using `-f -` stdin piping, zero temp files
3. `RealRuntimeValidator` — calls actual `docker build -f -` and `podman build -f -` with stdin pipe

#### Prototype Results

```
─── 1. CURRENT BUG: temp files leak on crash ───
  PASS | Crash during build leaves temp file behind: True
  PASS | Silent unlink() failure leaves temp file behind: True

─── 2. CURRENT CODE: temp file in context directory ───
  PASS | Normal build: no temp files left behind

─── 3. FIXED CODE: no temp files, stdin pipe ───
  PASS | Fixed build: no temp files created at all
  PASS | Fixed: input_data is the encoded Dockerfile
  PASS | Fixed: input_data is bytes
  PASS | Fixed: input_data decodes to correct Dockerfile

─── 4. Path-based build_file — no temp file needed ───
  PASS | Path-based: no input_data
  PASS | Path-based: no temp files in context

─── 5. No context directory — tar path ───
  PASS | Tar path: input_data is bytes
  PASS | Tar path: contains Containerfile
  PASS | Tar path: contains script.sh

─── 6. Edge cases ───
  PASS | Context path with files: no temp files
  PASS | Context path with empty files: no temp files

─── 7. REAL DOCKER VALIDATION ───
  PASS | docker build -f - works
  PASS | podman build -f - works

RESULTS: 17 PASSED, 0 FAILED, 0 SKIPPED
```

#### What the Prototype Validates

| Check | Result | Evidence |
|-------|--------|----------|
| Bug is real (crash leak) | ✅ Confirmed | SIGKILL simulation leaves file behind |
| Bug is real (silent cleanup failure) | ✅ Confirmed | Permission-denied unlink() silently swallowed |
| Fixed approach creates no temp files | ✅ Confirmed | Zero `Dockerfile.tmp.*` files in context directory |
| Path-based build_file unchanged | ✅ Confirmed | No input_data, no temp files |
| Tar path (no context) unchanged | ✅ Confirmed | Valid tar with correct tar_entry_name + files |
| `docker build -f -` works with real Docker | ✅ Confirmed | Returns valid sha256 image ID |
| `podman build -f -` works with real Podman | ✅ Confirmed | Returns valid image ID |

---

### Proposed Solution

#### Approach: Eliminate temp file via `-f -` stdin pipe

When `context.build_file` is a string and `context.context_path` is set, use `-f -` to tell Docker/Podman to read the Dockerfile from stdin, and pass the encoded content through the existing `input_data` parameter which is already piped to the subprocess's stdin.

This eliminates the temp file entirely — no file to leak on crash, no file to leave behind on cleanup failure, no pollution of the user's project directory.

**Update** `adapters/managers/image.py:30-37` — Replace the temp-file branch:
```python
elif context.context_path is not None:
    # Read Dockerfile from stdin — no temp file to leak
    cmd.extend(["-f", "-"])
    cmd.append(str(context.context_path))
    input_data = context.build_file.encode("utf-8")
```

**Remove** the entire `try/finally` (lines 26-56) — no temp file, no resources to clean up. The `build()` body becomes flat. Justification — resource trace of every line in the `try` body:

| Line(s) | Resource | Cleanup needed? | Reason |
|---------|----------|----------------|--------|
| 27-29 | `cmd` (local list) | ❌ No | GC collected |
| 30-37 | `temp_file` | ❌ No | **Eliminated by this fix** |
| 38-40 | `_create_tar()` | ❌ No | `with tarfile.open(...)` context-managed internally |
| 42-46 | `cmd` (list extend) | ❌ No | Local list, GC collected |
| 48 | `self._transport.execute()` | ❌ No | Finding #14 guarantees subprocess reaping |
| 48 | `input_data` (bytes) | ❌ No | Piped to subprocess stdin, closed by subprocess |
| 49 | `self._check_result()` | ❌ No | Read-only, no state |
| 50 | `self._parser.parse_build_output()` | ❌ No | Stateless parser |
| 50 | `self._decode_stdout()` | ❌ No | Pure decode, no I/O |

No resource in the `try` body needs a `finally` guarantee. The entire `try/finally` structure existed only for `temp_file`. Without it, the `try/finally` is dead scaffolding.

**Remove** the `import uuid` at line 32 — no longer needed.

#### Files to Touch

| File | Change |
|------|--------|
| `adapters/managers/image.py` | Lines 30-37: Replace temp-file creation with `-f -` + `input_data = context.build_file.encode("utf-8")`. Remove lines 26-56 (`try/finally` wrapper). Remove `import uuid` (line 32). Remove line 24 (`temp_file = None`). |

#### Tests to Add/Update

| File | Change | Reason |
|------|--------|--------|
| `tests/unit/adapters/test_cli_image_manager.py` | Add `test_build_with_context_path_creates_no_temp_files` | Validates zero `Dockerfile.tmp.*` files in context dir after build |
| `tests/unit/adapters/test_cli_image_manager.py` | Add `test_build_with_context_path_sends_encoded_dockerfile_via_input_data` | Validates `input_data` carries encoded Dockerfile content (not a tar) |
| `tests/unit/adapters/test_cli_image_manager.py` | Add `test_build_with_context_path_ignores_files_dict` | Validates `files` dict is still ignored when `context_path` is set (invariant preserved — `input_data` is plain encoded Dockerfile, not a tar bundling both) |
| `tests/integration/functional/test_workflows.py` | Verify build with context path still returns correct image ID | No temp file in cmd chain |

**No changes needed** to existing tests — the command output and return value are identical. The only change is how the Dockerfile content reaches Docker (stdin instead of a file path).

#### Hexagonal Architecture Compliance Check

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Domain: pure Python, no I/O | ✅ Unchanged | No domain types modified |
| Ports: ABCs only, no implementation | ✅ Unchanged | `ImageManager.build()` signature unchanged (`-> str`) |
| Adapters: implement contracts, contain I/O | ✅ | `-f -` + stdin piping — all I/O through existing transport channel |
| Adapters: orchestration only, no business logic | ✅ | Same orchestration: build command → execute → parse — no new logic |
| Factory: only DI composition root | ✅ Unchanged | No factory changes needed |
| Cleanup responsibility | ✅ Eliminated | No temp file = no cleanup needed. `finally` block removed entirely. |
| OS-level crash protection | ✅ Improved | Zero disk state = zero disk leak, regardless of failure mode |

The fix is an adapter-level change only. The `Transport.execute(input_data=...)` already pipes bytes to the subprocess stdin — this is an established pattern used by the tar path. Using it for Dockerfile content when a context directory is present is the same mechanism, just different content. The `files` dict behavior with `context_path` is unchanged (still ignored — files must exist on disk in the context directory).

No new dependencies, no new I/O patterns, no layer boundary crossings. The temp file branch is replaced with a zero-disk alternative that uses existing infrastructure.

#### Resolution

**Status:** ✅ RESOLVED
**Date:** 2026-06-03
**Changes applied:**

1. **`adapters/managers/image.py`** — Replaced the temp-file branch (when `context.build_file` is `str` and `context.context_path` is set) with `-f -` stdin piping: the build command receives `-f -` and `input_data = context.build_file.encode("utf-8")` passes the Dockerfile content through the existing transport stdin channel. Removed `temp_file = None`, removed `import uuid` (was inline in the `try` block), removed the entire `try/finally` block — no temp file means no disk state to leak on crash, no cleanup needed, no `except Exception: pass` to silently swallow unlink failures. The `build()` body is now flat.

2. **`tests/unit/adapters/test_cli_image_manager.py`** — Added `test_build_with_context_path_sends_encoded_dockerfile_via_input_data` (validates `input_data` carries `context.build_file.encode("utf-8")`) and `test_build_with_context_path_includes_f_dash` (validates the command includes `-f` followed by `-` for stdin).

**Solution rationale:** When `context.build_file` is a string and `context.context_path` is set, the old code wrote a `Dockerfile.tmp.<uuid>` inside the user's build context directory, then tried to clean it up in a `finally` block. Two leak scenarios existed: (1) SIGKILL between `write_text` and `unlink()` orphans the file permanently, and (2) the `except Exception: pass` on unlink() silently swallows cleanup failures. Using `-f -` tells Docker/Podman to read the Dockerfile from stdin, and passing the encoded content through the existing `input_data` parameter (already used by the tar path) eliminates the temp file entirely — zero disk state, zero leak, zero cleanup responsibility. This reuses established infrastructure: `Transport.execute(input_data=...)` already pipes bytes to the subprocess stdin.

**Verification:** 643 tests pass (0 failures) — 2 new unit tests added, all existing tests unchanged.

The pre-existing report at `docs/oci-runtime-audit-report.md` (now replaced) contained factual errors:

| Previous Claim | Truth |
|---|---|
| "Concrete Logic in Ports" — `BaseManager` in ports layer | **False.** `CliBaseManager` is in `adapters/managers/base.py` — correct adapters layer. No architecture violation. |
| "Fake Prune Returns" — hardcoded dicts | **False.** `BaseCliParser.parse_prune()` actually parses output correctly (regex on hex IDs + reclaimed space string). |
| "Missing PTY Support" — `execute_pty` unimplemented | **False.** `execute_pty` IS implemented at `cli.py:107-165`. However, it has critical bugs and is never called (see Finding #7). |
| Type confusion in RunConfig network/restart_policy | **False.** `_resolve_val()` in `base.py:22-28` correctly handles both `str` and `Enum` via duck-typing (`hasattr(val, "value")`) |
| Entrypoint argument ordering | **False.** `container.py:85-86` correctly places extra entrypoint args AFTER the image name |

---

## Findings Summary

| Severity | Count | Key Action |
|----------|-------|------------|
| 🔴 Critical | 4 (4 ✅ RESOLVED) | #18 ping() removed, #19 logs() streams via Iterator[str] |
| 🟠 High | 6 (6 ✅ RESOLVED) | #20: Factory lazy provider registration |
| 🟡 Medium | 7 (7 ✅ RESOLVED) | #21: ✅ RESOLVED — `hasattr` guard removed. #22: ✅ RESOLVED — `exec()` returns `ExecOutput` preserving stderr |
| 🔵 Low | 10 (7 ✅ RESOLVED, 3 🔵 OPEN) | #23: info() removed (📋 PLAN APPROVED). #24: Domain type inconsistencies — BuildContext.build_file split (📋 PLAN APPROVED). #25: ✅ RESOLVED — Mutable presets + contract contradiction fixed (frozen dataclass, required binary, no get_binary). #26: ✅ RESOLVED — Image temp file leak eliminated via `-f -` stdin pipe. |

**Total: 27 findings.** 24 resolved, 3 open. See findings #23–#26 above for details.

---
