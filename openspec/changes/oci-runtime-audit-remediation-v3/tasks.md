## Phase T1 — Domain scaffolding (additive, no behavior change)

- [x] 1.1 Create `src/oci_runtime/domain/build_tar.py` — `create_build_tar`, `_validate_tar_path` from `adapters/_tar.py`; fix regex
- [x] 1.2 Create `src/oci_runtime/domain/size_parsing.py` — `parse_size_to_bytes`, `coerce_size`, `safe_int` from `adapters/_utils.py`; add unitless + whitespace support
- [x] 1.3 Create `src/oci_runtime/domain/json_parsing.py` — `parse_json_item(raw) -> dict` (with scalar+length guard per A2), `parse_json_list(raw) -> list[dict]`
- [x] 1.4 Create `src/oci_runtime/domain/error_matching.py` — `matches_any_pattern(text, patterns) -> bool`
- [x] 1.5 Create `src/oci_runtime/domain/prune_parsing.py` — `parse_prune_result(raw) -> PruneResult`
- [x] 1.6 Create `src/oci_runtime/domain/list_command.py` — `build_list_command(binary, subcommand, format_flags, show_all, filters) -> list[str]`
- [x] 1.7 Create `src/oci_runtime/domain/encoding.py` — `safe_decode(data: bytes) -> str`
- [x] 1.8 Create `src/oci_runtime/domain/result_checking.py` — `check_cli_result(result, cmd, *, operation, entity, not_found_error, generic_error, auth_error, is_auth, is_not_found) -> None`
- [x] 1.9 Create `src/oci_runtime/ports/result_checker.py` — `ResultChecker` ABC: `check(result, cmd, *, operation, entity, not_found_error) -> None`
- [x] 1.10 Create `src/oci_runtime/ports/list_executor.py` — `ListExecutor[T]` ABC: `execute_list(subcommand, entity_type, *, show_all, filters) -> list[T]`
- [x] 1.11 Create `src/oci_runtime/adapters/helpers/result_checker.py` — `CliResultChecker(ResultChecker)`: receives error types + callables via constructor
- [x] 1.12 Create `src/oci_runtime/adapters/helpers/list_executor.py` — `CliListExecutor[T](ListExecutor[T])`: receives transport, caps, ResultChecker, parse_list via constructor
- [x] 1.13 Update `ports/cancellation.py` — add `CompositeCancellationToken` + `compose_tokens()` (moved from adapters; pure logic, no I/O)
- [x] 1.14 Add re-export shims in `adapters/_tar.py` and `adapters/_utils.py` (`from oci_runtime.domain.build_tar import *`, etc.) — temporary, deleted in T4
- [x] 1.15 Update `src/oci_runtime/ports/__init__.py` — export `ResultChecker`, `ListExecutor`; stop exporting `Managers`
- [x] 1.16 Update `src/oci_runtime/domain/__init__.py` — export new domain helpers
- [x] 1.17 Run `make check` — all 840 tests green, no behavior change

## Phase T2 — Rewire parsers (import realignment, delete BaseCliParser)

- [x] 2.1 Update `adapters/parser/docker.py`:
  - Remove `from oci_runtime.adapters.parser.base import BaseCliParser, _coerce_size, _safe_int`
  - Each concrete parser implements port ABC directly (`class DockerContainerParser(ContainerParser)`, not `(BaseCliParser, ContainerParser)`)
  - Add `from oci_runtime.domain.json_parsing import parse_json_item, parse_json_list`
  - Add `from oci_runtime.domain.error_matching import matches_any_pattern`
  - Add `from oci_runtime.domain.prune_parsing import parse_prune_result`
  - Add `from oci_runtime.domain.size_parsing import coerce_size, safe_int`
  - Each parser implements `is_not_found_error` via `matches_any_pattern(stderr, self._not_found_patterns)`
  - Each parser implements `parse_prune` via `parse_prune_result(raw)`
  - `DockerImageParser`/`PodmanImageParser` additionally implement `is_auth_error` via `matches_any_pattern(stderr, self._auth_error_patterns)`
- [x] 2.2 Same refactor for `adapters/parser/podman.py`
- [x] 2.3 Delete `adapters/parser/base.py` once all references removed
- [x] 2.4 Run `make check` — all tests green, parsers no longer depend on BaseCliParser

## Phase T3 — Rewire managers (delete CliBaseManager, inject ResultChecker + ListExecutor)

- [x] 3.1 Update `adapters/managers/container.py`:
  - Remove `from oci_runtime.adapters.managers.base import CliBaseManager`
  - Implement `ContainerManager` directly (no `CliBaseManager` inheritance)
  - Add `result_checker: ResultChecker` and `list_executor: ListExecutor[ContainerInfo]` to constructor
  - Store them as `self._result_checker` and `self._list_executor`
  - Replace all `self._check_result(result, cmd, ...)` calls with `self._result_checker.check(result, cmd, ...)`
  - Replace `self._decode_bytes(data)` with `safe_decode(data)` from domain
  - `list()` becomes: `return self._list_executor.execute_list(["container", "list"], "containers", show_all=show_all, filters=filters)`
  - `exec_container()` retains direct `self._parser.is_not_found_error(stderr_str)` call (intentional bypass)
- [x] 3.2 Same refactor for `adapters/managers/image.py`:
  - Remove CliBaseManager inheritance
  - Inject `ResultChecker` + `ListExecutor[ImageInfo]`
  - `pull()` raises `ImageRuntimeError` on digest failure (A6) via direct raise (post-check business logic)
- [x] 3.3 Same refactor for `adapters/managers/volume.py`:
  - Inject `ResultChecker` + `ListExecutor[VolumeInfo]`
- [x] 3.4 Same refactor for `adapters/managers/network.py`:
  - Inject `ResultChecker` + `ListExecutor[NetworkInfo]`
- [x] 3.5 Delete `adapters/managers/base.py` once all references removed
- [x] 3.6 Run `make check` — all tests green

## Phase T4 — Rewire providers + factory DI (delete BaseCliRuntimeProvider)

- [x] 4.1 Update `adapters/provider/docker.py`:
  - Remove `from oci_runtime.adapters.provider._base import BaseCliRuntimeProvider`
  - Implement `RuntimeProvider` directly with constructor injection of parser classes + capabilities
  - Define `_DOCKER_CAPABILITIES = RuntimeCapabilities(...)` at module level
- [x] 4.2 Same refactor for `adapters/provider/podman.py`
- [x] 4.3 Delete `adapters/provider/_base.py` once all references removed
- [x] 4.4 Update `factory.py`:
  - Create per-manager `CliResultChecker` instances with appropriate error types + parser callables
  - Create per-manager `CliListExecutor[T]` instances with transport, caps, same ResultChecker, parser.parse_list
  - Pass `result_checker` and `list_executor` to each manager constructor
  - Pass parser classes + capabilities to each provider constructor (in `_default_providers`)
  - Add `result_checker_factory` and `list_executor_factory` to `RuntimeFactoryConfig` (default to `CliResultChecker` / `CliListExecutor`)
  - Tighten transport factory signatures (second arg `BinaryResolver` required)
- [x] **4.5-4.6 deferred**: transport_factory.py + CliTransport test migration (medium priority, non-blocking)
- [x] **4.7 deferred**: architecture linter tightening (requires internal adapter cleanup in T6)
- [x] 4.8 Run `make check` — 851 passed, 1 skipped

## Phase T5 — Audit bug fixes (one commit per bug)

- [x] 5.1 **A1 host_ip**: Update `CliContainerManager.run()` port-flag builder; update Docker/Podman container parsers to map empty `HostIp` → `None`, explicit `"0.0.0.0"` → `"0.0.0.0"`
- [x] 5.2 **A1 test**: Add `tests/audit/test_known_bugs.py::TestA01HostIpLoopbackBinding`; fix existing wiring tests
- [x] 5.3 **A2 _parse_json_item guard**: Already implemented in `domain/json_parsing.parse_json_item()` (T1.3). Add conformance regression test feeding scalars
- [x] 5.4 **A3 ProcessPipeReader strict**: Delete fallback branch in `_read_fd`; `from_process` raises `TypeError` if `fileno()` fails
- [x] 5.5 **A3 test**: Add test that `BytesIO`/`MagicMock` input raises `TypeError`
- [x] 5.6 **A4 _check_result simplification**: Already done via `CliResultChecker.check()` (T3). Drop `getattr` + `is_auth is not None` guard; attach `command`/`exit_code`/`stderr` to `ImagePullAccessDeniedError` (requires change to exception's `__init__`)
- [x] 5.7 **A5 PTY empty command**: Change `CliPtyTransport.execute_pty` to raise `OciError` instead of `ContainerRuntimeError`
- [x] 5.8 **A6 pull()**: `CliImageManager.pull()` raises `ImageRuntimeError` with context on digest failure; add audit regression test
- [x] 5.9 **A7 version()**: `CliRuntime.version()` raises `OciError` with full context; propagate `OperationTimeoutError`
- [x] 5.10 **A7 test**: Migrate existing `test_version_raises_on_nonzero` to expect `OciError`
- [x] 5.11 **A8 Managers aggregate**: Delete `Managers` from `ports/aggregates.py`; remove from exports; delete unused imports
- [x] 5.12 Run `make check` — 859 passed, 1 skipped

## Phase T6 — Test quality + doc drift cleanup

- [x] 6.1 **D1/D6**: Rewrite `test_run_with_all_options` — assert correct `-p` forms with `host_ip` (done in T5.2)
- [x] 6.2 **D2**: Fix `test_parsers_is_frozen_dataclass` — use correct parser types per slot
- [x] 6.3 **D3**: Expand `test_factory_config_defaults_are_none` to assert all fields are `None`
- [x] 6.4 **D4**: Fix `test_custom_transport_factory_is_used` — use tuple key `("docker", "--version")`
- [x] 6.5 **D5**: Delete dead `@patch("subprocess.run")` decorators
- [x] 6.6 **D7**: Replace `isinstance` with port types (done in T5)
- [x] 6.7 **D8**: Add `test_result_checker_requires_error_types` + `test_list_executor_parse_list_callable`
- [x] 6.8 **D9**: Add conformance fixture warning in `conftest.py`
- [x] 6.9 **D10**: Remove redundant `_safe_int` calls
- [x] 6.10 **E1**: Update `ARCHITECTURE.md` routing matrix + remove stale sections
- [x] 6.11 **E2**: Note domain-based scalar guard in remediation log
- [x] 6.12 **E3**: Remove stale "subprocess.run" from docstring
- [x] 6.13 **E5**: Update `ports/managers.py` timeout params
- [x] 6.14 **E5**: Update manager implementations to match
- [x] 6.15 **E6**: Add remediation log entry for v3 in `ARCHITECTURE.md`
- [x] 6.16 **C1**: All `list()` are 1-line delegates (verified in T3)
- [x] 6.17 **C2**: Delete `_NOT_PROBED` from binary.py
- [x] 6.18 **C3**: Tighten `RuntimeFactoryConfig` annotations
- [x] 6.19 **C5**: Fix `_validate_tar_path` norm check
- [x] 6.20 **C6**: `parse_size_to_bytes` unitless (done in T1.2)
- [x] 6.21 **F1**: `--network bridge` + `LogDriverNotSupportedWarning`
- [x] 6.22 Run `make check` — 861 passed, 1 skipped

## Phase T7 — Conformance + integration (optional validation)

- [x] 7.1 Run `make capture-fixtures` on a machine with both docker and podman — 16 fixtures captured
- [x] 7.2 Run full `pytest tests/conformance/ -v` — 31 passed, 1 skipped (podman network inspect fixture pending)
- [x] 7.3 Run `pytest tests/integration/smoke/ -v` — 8 passed (factory creation, version, container/volume/network lifecycle)
- [x] 7.4 Final `make check` — **861 passed, 1 skipped**, zero linter warnings
