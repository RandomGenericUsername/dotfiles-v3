# Remaining Audit Remediation Plan

**Date:** 2026-06-11
**Scope:** Remaining findings after list_format_flags fix + H4 (PortMapping.host_ip default)

---

## What is Already Implemented (do not re-do)

- **list_format_flags**: `supported_output_formats` replaced with capability-driven `list_format_flags` in all 4 managers, both providers, NDJSON fallback in `_parse_json_list()`, key normalization in all parser `parse_list()` methods
- **H4: PortMapping.host_ip default**: domain default changed to `"0.0.0.0"`, both Docker/Podman port parsers normalize empty `HostIp` → `0.0.0.0`, test assertion updated

---

## Remaining Items

---

### H6: ContainerState ValueError on Unknown States

| Field | Value |
|-------|-------|
| **Severity** | High |
| **Layer** | Domain (`enums.py`) |
| **Files** | `src/oci_runtime/domain/enums.py`, `tests/unit/domain/test_enums.py` |

**Current behavior:**
`ContainerState("unknown")` raises `ValueError` because `ContainerState` is a `StrEnum` with only 7 closed members. If Docker/Podman introduce a new state (e.g., "deleting") or return an unexpected string, the parser crashes at runtime.

**Problem:**
Enums with runtime data sources should have a fallback for values outside the known set. The parser code (`docker.py:29`, `docker.py:45`, `podman.py:61`, `podman.py:77`) does `ContainerState(item.get(...))` which means ANY unhandled state string from the runtime crashes the process.

**Solution — Add `_missing_` fallback to ContainerState:**

1. Add a `UNKNOWN = "unknown"` member to `ContainerState`
2. Override `_missing_` classmethod to return `ContainerState.UNKNOWN`
3. Update the "closed set" test to include `"UNKNOWN"` in expected members
4. Update the "unknown state raises ValueError" test to instead assert fallback to `UNKNOWN`
5. Update the "empty string raises ValueError" test similarly

```
class ContainerState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    REMOVING = "removing"
    EXITED = "exited"
    DEAD = "dead"
    UNKNOWN = "unknown"                                   # NEW

    @classmethod
    def _missing_(cls, value: object) -> "ContainerState":  # NEW
        return cls.UNKNOWN                                  # NEW
```

**Test changes:**
```python
# test_enums.py
def test_unknown_state_raises_value_error(self):           # RENAME
    result = ContainerState("unknown")                     # was: with pytest.raises(ValueError)
    assert result is ContainerState.UNKNOWN                # was: ContainerState("unknown")

def test_empty_string_raises_value_error(self):            # RENAME
    result = ContainerState("")                            # was: with pytest.raises(ValueError)
    assert result is ContainerState.UNKNOWN                # was: ContainerState("")

def test_closed_set_engine_states(self):                   # UPDATE
    members = set(ContainerState.__members__)
    assert members == {
        "CREATED", "RUNNING", "PAUSED", "RESTARTING",
        "REMOVING", "EXITED", "DEAD", "UNKNOWN"            # ADDED
    }
```

No parser changes needed — they already do `ContainerState(item.get(...))` which will hit `_missing_` for unknown values.

---

### M1: `parse_size_to_bytes` Returns 0 on Unparseable Input

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Layer** | Adapter — Parser (`base.py`) |
| **Files** | `src/oci_runtime/adapters/parser/base.py`, `src/oci_runtime/adapters/parser/docker.py`, `tests/unit/adapters/test_parser_base.py` |

**Current behavior:**
`parse_size_to_bytes("9999")` returns `0`. `parse_size_to_bytes("")` returns `0`. A legitimate 0-byte file also returns `0`.

**Problem:**
The return value `0` is ambiguous — cannot distinguish "unparseable input" from "real zero-byte size." Docker `image ls --format '{{json .}}'` uses `VirtualSize` as a numeric field (int), and `Size` as either human string ("8.45MB") or numeric. Returning 0 on parse failure silently hides data corruption — a 2GB image appears as 0 bytes.

**Solution — raise ValueError, handle at callers:**

1. Make `parse_size_to_bytes` raise `ValueError` when the input cannot be parsed
2. Catch the `ValueError` in `parse_prune()` where we already call it
3. In the Docker image parser, catch `ValueError` around `parse_size_to_bytes` calls and default to 0 (since the field may be a numeric type, not a string)

```
def parse_size_to_bytes(size_str: str) -> int:
    match = re.search(r"(\d+\.?\d*)\s*([a-zA-Z]+)", size_str.upper())
    if not match:
        raise ValueError(f"Cannot parse size: {size_str}")   # CHANGED: was `return 0`
    number, unit = match.groups()
    ...
```

**Docker parser changes** (`docker.py` ImageParser.parse_list):

```python
size = item.get("Size", 0)
if isinstance(size, str):
    try:
        size = parse_size_to_bytes(size)
    except ValueError:                      # NEW: guard
        size = 0
if not size:
    virtual = item.get("VirtualSize", 0)
    if isinstance(virtual, str):
        try:
            size = parse_size_to_bytes(virtual)
        except ValueError:                  # NEW: guard
            size = 0
    else:
        size = virtual
```

**Test changes** (`test_parser_base.py`):

```python
def test_returns_zero_for_empty_string(self):        # RENAME + UPDATE
    with pytest.raises(ValueError):                   # was: assert parse_size_to_bytes("") == 0
        parse_size_to_bytes("")

def test_returns_zero_for_no_unit(self):              # RENAME + UPDATE
    with pytest.raises(ValueError):                   # was: assert parse_size_to_bytes("9999") == 0
        parse_size_to_bytes("9999")

# Also add tests in test_docker_parser.py to verify the ValueError is
# caught in parse_list and falls back to 0
```

---

### M4: Missing `operation` in `_check_result()` Calls

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Layer** | Adapter — Manager |
| **Files** | `src/oci_runtime/adapters/managers/volume.py`, `src/oci_runtime/adapters/managers/network.py` |

**Current behavior:**
`volume.py:41` and `network.py:51` call `_check_result(result, cmd, entity=name, not_found=...)` without the `operation=` keyword argument. The parameter defaults to `"execute command"` (defined in `base.py:30`).

**Problem:**
Error messages from inspect failures say `"Failed to execute command"` instead of `"Failed to inspect volume"` or `"Failed to inspect network"`. This makes debugging harder — the operator doesn't know which operation failed.

**Solution — add descriptive `operation` strings:**

Volume manager (`volume.py:41`):
```python
self._check_result(result, cmd, operation="inspect volume", entity=name, not_found=VolumeNotFoundError)
```

Network manager (`network.py:51`):
```python
self._check_result(result, cmd, operation="inspect network", entity=name, not_found=NetworkNotFoundError)
```

**No test changes needed** unless tests explicitly check error message content.

---

### L6: `RuntimeCapabilities` Should Be Frozen

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Layer** | Port (`capabilities.py`) |
| **Files** | `src/oci_runtime/ports/capabilities.py`, `tests/integration/capability/test_capabilities.py`, `tests/integration/contract/test_interface_compliance.py` |

**Current behavior:**
`RuntimeCapabilities` is a plain `@dataclass` (mutable). `RuntimePreference` alongside it is `@dataclass(frozen=True)`. Two tests explicitly verify mutability by doing `caps.supports_log_drivers = False`.

**Problem:**
Capabilities represent runtime-identified characteristics that should not change during the lifetime of the object. Mutable capabilities are a code smell — they invite state mutation bugs and make the object inconsistent. `RuntimePreference` is already frozen; `RuntimeCapabilities` should follow the same convention.

**Solution — freeze the dataclass and update tests:**

```python
@dataclass(frozen=True)  # CHANGED: was @dataclass
class RuntimeCapabilities:
    list_format_flags: list[str] = field(default_factory=list)
    ...
```

**Test changes:**

File `tests/integration/capability/test_capabilities.py`:
```python
def test_runtime_capabilities_is_frozen(self):              # RENAME
    caps = RuntimeCapabilities()
    with pytest.raises(FrozenInstanceError):                # CHANGED
        caps.supports_log_drivers = False                   # was: assert caps.supports_log_drivers is False
```

Update the import to include `FrozenInstanceError` from `dataclasses`.

File `tests/integration/contract/test_interface_compliance.py`:
```python
def test_runtime_capabilities_is_frozen(self):               # RENAME
    caps = RuntimeCapabilities()
    with pytest.raises(FrozenInstanceError):                 # CHANGED
        caps.supports_log_drivers = False                    # was: assert caps.supports_log_drivers is False
```

---

### L7: `run_pty` Default `on_output` Writes to stdout Instead of Returning

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Layer** | Adapter — Manager (`pty.py`) |
| **Files** | `src/oci_runtime/adapters/managers/pty.py`, `tests/unit/adapters/test_cli_pty.py` |

**Current behavior:**
`run_pty()` in `pty.py:17-28` has `on_output: Callable[[bytes], None] | None = None`. When `None`, it defaults to `_default_pty_output` which writes directly to `sys.stdout.buffer`:

```python
def _default_pty_output(data: bytes) -> None:
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()
```

The returned `CompletedProcess` always has empty `stdout=b""`/`stderr=b""`.

**Problem:**
By default, PTY output is written directly to stdout with no way to capture it programmatically. The container manager (`container.py:102-103`) calls `execute_pty(cmd)` which returns `CompletedProcess` with empty stdout — the container ID (emitted by Docker/Podman on stdout after `docker run -t`) is lost, so `run()` returns `""` in PTY mode.

**Solution — always buffer alongside the existing callback:**

Keep the existing real-time stdout streaming intact (no breaking change), but also buffer all output into a `bytearray` that's returned as `CompletedProcess.stdout`:

```python
def run_pty(
    command: list[str],
    on_output: Callable[[bytes], None] | None = None,
) -> subprocess.CompletedProcess:
    ...
    output_buffer = bytearray()                            # NEW

    if on_output is None:
        def _handler(data: bytes) -> None:                 # NEW: replaces _default_pty_output
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
            output_buffer.extend(data)
        on_output = _handler
    else:
        _orig = on_output
        def _wrapped(data: bytes) -> None:                 # NEW: wraps custom callback
            _orig(data)                                    # still calls original in real time
            output_buffer.extend(data)                     # also buffers
        on_output = _wrapped

    # ... rest of PTY loop unchanged ...

    return subprocess.CompletedProcess(
        args=command, returncode=proc.returncode,
        stdout=bytes(output_buffer), stderr=b"",            # CHANGED: was stdout=b""
    )
```

**Why this works:**
- **Default behavior unchanged** — output still streams to stdout in real time, no breaking change for interactive users
- **`result.stdout` is now populated** — callers can access the full container output programmatically (e.g., the container ID from `docker run -t`)
- **Custom `on_output` callbacks still work** — the original callback is called with every chunk in real time, AND the data is silently buffered
- **No `stream` parameter needed** — avoids API bloat

**Test changes:**
- `test_basic_execution_returns_completed_process` — assert `result.stdout` is non-empty (was `b""`)
- `test_run_pty_default_writes_to_stdout` — remains valid (output still written to stdout)
- `test_run_pty_calls_on_output_callback` — remains valid (custom callback still invoked)
- Add: `test_pty_output_buffered_in_stdout_field` — new test verifying output is available on `result.stdout`

---

### L8: `NetworkMode.CONTAINER` Lacks Container Argument in `run()`

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Layer** | Domain + Adapter — Manager |
| **Files** | `src/oci_runtime/domain/types.py`, `src/oci_runtime/domain/enums.py`, `src/oci_runtime/adapters/managers/container.py`, `tests/unit/domain/test_types.py`, `tests/unit/adapters/test_cli_container_manager.py` |

**Current behavior:**
When `config.network == NetworkMode.CONTAINER`, the container manager emits `--network container` (from `str(config.network)` in `container.py:55`). Docker/Podman require `--network container:<container_id>`.

**Problem:**
`NetworkMode.CONTAINER` cannot work without specifying which container to share the network namespace with. The enum value alone is insufficient — it needs an argument (container name or ID). Current code silently produces a broken command.

**Solution — Add `network_container` field to `RunConfig`:**

1. Add `network_container: str | None = None` to `RunConfig`
2. In `container.py:run()`, when `network == NetworkMode.CONTAINER`:
   - If `config.network_container` is set, emit `--network container:{network_container}`
   - If `config.network_container` is None, raise `ContainerRuntimeError` with a clear message

**Domain changes** (`types.py`):

```python
@dataclass
class RunConfig:
    ...
    network: NetworkMode = NetworkMode.BRIDGE
    network_container: str | None = None       # NEW
    ...
```

**Manager changes** (`container.py:53-55`):

```python
if config.network:
    if config.network == NetworkMode.CONTAINER:
        if not config.network_container:
            raise ContainerRuntimeError(
                "network=CONTAINER requires network_container to be set",
            )
        cmd.extend(["--network", f"container:{config.network_container}"])
    elif config.network != NetworkMode.BRIDGE:
        cmd.extend(["--network", str(config.network)])
```

**Test changes:**

Update `tests/unit/domain/test_types.py` — add tests for:
- `test_network_container_default_is_none`
- `test_network_container_accepts_string`
- `test_network_container_and_bridge_compatible`

Update `tests/unit/adapters/test_cli_container_manager.py` — add tests for:
- `test_run_network_container_requires_arg` — CONTAINER without `network_container` raises error
- `test_run_network_container_adds_flag` — CONTAINER with `network_container="nginx"` produces `--network container:nginx`
- `test_run_network_bridge_does_not_use_container_arg` — BRIDGE mode ignores `network_container`

---

### Podman Network `scope` Field

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Layer** | Adapter — Parser (`podman.py`) |
| **Files** | `src/oci_runtime/adapters/parser/podman.py` (already handled) |

**Current behavior:**
The PodmanNetworkParser already handles missing `scope` with `scope = item.get("Scope") or item.get("scope", "")` at `podman.py:189`. No scope key exists in Podman `network ls --format json` output.

**Finding:**
Podman network ls output does not include a `scope` attribute, so the `NetworkInfo.scope` field is always `""` for list results. This is already handled correctly by the parser.

**Decision:**
No action needed — the parser already degrades gracefully to empty string. The empty scope is semantically correct (Podman has no Swarm concept, so "local" is implicit). Document this as accepted behavior.

---

## Implementation Order

1. **H6** — ContainerState — domain change only, no ripple effects
2. **L8** — NetworkMode.CONTAINER — touches domain+manager, affects test assertions
3. **M4** — Missing operation params — simplest change, two lines
4. **M1** — parse_size_to_bytes — moderate impact, touches base + docker parser + tests
5. **L6** — RuntimeCapabilities frozen — simple change, updates 2 tests
6. **L7** — run_pty output collection — moderate impact, pty.py redesign + test updates

## Verification

After implementing each item:
```bash
cd src/shared/oci-runtime && python -m pytest tests/ -x -q --tb=short
```

All 694+ tests must pass after the full set of changes.
