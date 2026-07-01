## Why

Commit `1953540` ("relocate cancellation & pipe_reader to ports, add is_auth_error to parser ABCs") fixed real hexagonal-architecture drifts (AUDIT-v3 B1/B2) — removing adapter→adapter imports and internal fallback instantiation. However, it introduced 3 regressions and left ~15 AUDIT-v3 findings unresolved:

**Regressions (new crashes):**
1. `CliPtyTransport.execute_pty` crashes with `AttributeError` when `output_stream=None` — the `StdoutBufferStream` fallback was removed but the `| None` type hint was kept
2. `CliTransport.execute` and `CliStreamingTransport.stream` crash with `AttributeError` when `binary_resolver=None` — same pattern: `or CliBinaryResolver()` removed, `| None` kept
3. `CliContainerManager.exec_container` now swallows ALL `ContainerRuntimeError` via broad `except ContainerRuntimeError: pass` — the old code only suppressed not-found errors; the new code masks permission errors, corrupted state, and other real failures

**AUDIT-v3 findings still open:**
- A1: `PortMapping.host_ip` silently dropped (security-relevant — loopback binding becomes host-wide)
- A8/E4: `Managers` aggregate is dead code; doc still advertises `create_managers`
- C1: `_execute_list` dead code; doc claims dedup that never happened
- C2: `_NOT_PROBED` dead sentinel
- C4: Stale `subprocess.run` docstring in `ports/streaming.py`
- E5: Timeout types inconsistent (`int` vs `float`) across manager ABCs
- D2-D5, D7: Test quality issues (wrong types, dead mocks, broken dict keys)

This change fixes all 3 regressions, resolves the remaining AUDIT-v3 findings, and adds targeted tests to prevent recurrence.

## What Changes

### Regression Fixes (R series)

- **R1**: `CliPtyTransport.__init__` requires `output_stream: OutputStream` (not `| None`). Factory always provides it; the `None` lie is the crash source.
- **R2**: `CliTransport.__init__` and `CliStreamingTransport.__init__` require `binary_resolver: BinaryResolver` (not `| None`). Same rationale.
- **R3**: `CliContainerManager.exec_container` narrows the `except` to only suppress `ContainerNotFoundError` — the intended behavior. All other `ContainerRuntimeError` subtypes propagate.

### AUDIT-v3 Fixes (A series, still open)

- **A1**: `CliContainerManager.run()` honors `PortMapping.host_ip` — emits `-p <host_ip>:<host_port>:<container_port>/<protocol>` when `host_ip is not None`.
- **A8/E4**: Delete unused `Managers` aggregate from `ports/aggregates.py`. Update `ARCHITECTURE.md` to remove `create_managers` documentation.
- **C1**: Delete dead `_execute_list` from `adapters/managers/base.py` (or delete the file if it becomes empty). Update ARCHITECTURE.md claim.
- **C2**: Delete `_NOT_PROBED` sentinel from `adapters/binary.py`.
- **C4**: Remove stale "subprocess.run" reference from `ports/streaming.py` docstring.
- **E5**: Unify timeout types across `ports/managers.py` — all `float | None`.

### Test Quality (D series)

- **D2**: Fix `test_parsers_is_frozen_dataclass` — use correct parser types per slot.
- **D3**: Expand `test_factory_config_defaults_are_none` to assert all fields.
- **D4**: Fix broken `"docker --version"` dict key to tuple.
- **D5**: Drop dead `@patch("subprocess.run")` decorators.
- **D7**: Replace `isinstance(runtime.images, CliImageManager)` with port-type assertions.

### New Regression Tests

- **T1**: Test `CliPtyTransport.execute_pty` with explicit `output_stream` (verifies R1).
- **T2**: Test `CliTransport.execute` with explicit `binary_resolver` (verifies R2).
- **T3**: Test `exec_container` propagates non-not-found `ContainerRuntimeError` (verifies R3).
- **T4**: Test `host_ip` round-trip in port flag building (verifies A1).

## Capabilities

### Modified Capabilities

- `oci-strict-hexagonal-layering`: Transport constructors now enforce required DI (no `None` fallback).
- `oci-port-binding-strictness`: `host_ip` honored end-to-end (A1 fix).
- `oci-exception-typing`: `exec_container` no longer swallows real errors.
- `oci-test-contracts`: New regression tests for R1-R3 and A1.

## Impact

- **Code**: 6 source files modified (pty.py, cli.py, streaming.py, container.py, base.py, binary.py).
- **Tests**: ~10 tests added/modified.
- **Public API**: Constructor signatures change (remove `| None` from 3 classes) — internal breaking, no external API surface.
- **Architecture**: No structural changes. Fixes drift introduced by 1953540.
- **Dependencies**: None.
- **Risk**: Low — each fix is a targeted signature change + narrow except clause.
