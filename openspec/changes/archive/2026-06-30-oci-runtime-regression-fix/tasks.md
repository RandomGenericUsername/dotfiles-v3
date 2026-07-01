# Implementation Tasks

> **Execution rules:**
> - Each phase leaves the test suite green
> - Run `make check` after each phase
> - One commit per phase

## Phase T1 — Regression fixes (R1-R3)

- [x] 1.1 **R1 — PTY output_stream required**: In `adapters/transport/pty.py:29`, change `output_stream: OutputStream | None = None` to `output_stream: OutputStream`. Remove `None` from type hint.
- [x] 1.2 **R2 — Transport binary_resolver required**: In `adapters/transport/cli.py:19`, change `binary_resolver: BinaryResolver | None = None` to `binary_resolver: BinaryResolver`. In `adapters/transport/streaming.py:18`, same change.
- [x] 1.3 **R3 — Narrow exec_container except**: In `adapters/managers/container.py:355`, change `except ContainerRuntimeError:` to `except ContainerNotFoundError:`.
- [x] 1.4 **Update factory wiring**: In `factory.py`, verify all transport factory callables pass `binary_resolver=` as keyword arg (not positional). The factory already does this — just verify no `None` flows through.
- [x] 1.5 **Fix PTY test signatures**: Update `tests/unit/adapters/test_cli_pty.py` to always pass `output_stream=` explicitly.
- [x] 1.6 **Fix transport test signatures**: Update `tests/unit/adapters/test_cli_transport.py` and `test_cli_streaming_transport.py` to always pass `binary_resolver=` explicitly.
- [x] **Verify 1:** `make check` — all tests green

## Phase T2 — Host_ip fix (A1)

- [x] 2.1 **Fix port flag building**: In `adapters/managers/container.py:110-116`, update the `-p` flag builder:
  ```python
  for port in config.ports:
      proto = port.protocol or "tcp"
      if port.host_ip is not None:
          if port.host_port is not None:
              flag = f"{port.host_ip}:{port.host_port}:{port.container_port}/{proto}"
          else:
              flag = f"{port.host_ip}::{port.container_port}/{proto}"
      else:
          if port.host_port is not None:
              flag = f"{port.host_port}:{port.container_port}/{proto}"
          else:
              flag = str(port.container_port)
      cmd.extend(["-p", flag])
  ```
- [x] 2.2 **Add regression test**: In `tests/audit/test_known_bugs.py`, add `TestA01HostIpLoopbackBinding` with 4 cases: host_ip+host_port, host_ip only, host_port only, neither.
- [x] 2.3 **Fix existing wiring tests**: Update `tests/unit/wiring/test_manager_commands.py:175,193` and `test_workflows.py:161,156` to assert correct `-p` forms.
- [x] **Verify 2:** `make check` — all tests green, host_ip tests pass

## Phase T3 — Delete dead code (C1, C2, A8)

- [x] 3.1 **Delete `_execute_list`**: Already deleted (file `adapters/managers/base.py` does not exist).
- [x] 3.2 **Delete `_NOT_PROBED`**: Already removed from `adapters/binary.py`.
- [x] 3.3 **Delete `Managers` aggregate**: Already removed from `ports/aggregates.py` and `ports/__init__.py`.
- [x] 3.4 **Update ARCHITECTURE.md**: No live references remain. Remediation log updated.
- [x] **Verify 3:** `make check` — all tests green

## Phase T4 — Doc/type drift (C4, E5)

- [x] 4.1 **Fix stale docstring**: Already updated (docstring uses "Popen + selector-based reading").
- [x] 4.2 **Unify timeout types**: Already done (all `float | None` in ports and adapters).
- [x] **Verify 4:** `make check` — all tests green

## Phase T5 — Test quality (D2-D5, D7)

- [x] 5.1 **D2 — Fix parser type test**: Updated `test_parsers_is_frozen_dataclass` to use Podman parsers.
- [x] 5.2 **D3 — Expand config defaults test**: Already asserts all 13 fields (already complete).
- [x] 5.3 **D4 — Fix broken dict key**: Already using tuple keys (already complete).
- [x] 5.4 **D5 — Drop dead mocks**: Removed `@patch("subprocess.run")` from `test_available_returns_list_of_preferences`.
- [x] 5.5 **D7 — Port-type assertions**: Already using port-type ABCs (already complete).
- [x] **Verify 5:** `make check` — all tests green

## Phase T6 — Regression tests (T1-T4)

- [x] 6.1 **T1 — PTY output_stream test**: Added `TestT01PtyOutputStream` in `test_known_bugs.py`.
- [x] 6.2 **T2 — Transport binary_resolver test**: Added `TestT02TransportBinaryResolver` in `test_known_bugs.py`.
- [x] 6.3 **T3 — exec_container error propagation test**: Added `TestT03ExecContainerErrorPropagation` in `test_known_bugs.py`.
- [x] 6.4 **T4 — host_ip round-trip test**: Added A1 port flag test cases in `TestA01HostIpLoopbackBinding`.
- [x] **Verify 6:** `make check` — all tests green, new regression tests pass

## Final verification

- [x] F.1 **Full suite**: `make check` — 868 passed, 1 skipped ✓
- [x] F.2 **Linter**: `make lint` — no warnings ✓
- [x] F.3 **Layering**: `python tests/architecture/test_layering.py` — 62 passed ✓
