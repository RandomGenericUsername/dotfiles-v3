## Why

A full audit of `oci-runtime` (840 tests passing, 1 skipped) surfaced 8 critical bugs that the test suite actively masks, 3 hexagonal-architecture drifts (the architecture linter allows adapter→adapter imports; transports internally instantiate sibling adapters; the `Managers` port aggregate is dead code while docs still advertise a `create_managers` API), and 13 medium/low issues spanning dead defensive code, stale docs, and tests that assert buggy behavior rather than correct behavior. Two findings are security-relevant (`PortMapping.host_ip="127.0.0.1"` is silently dropped by `CliContainerManager.run`, producing a `0.0.0.0` host binding instead of loopback-only) and exception-hierarchy violations (`_parse_json_item` returns scalar JSON, `CliPtyTransport` raises `ContainerRuntimeError` from a generic transport) that escape the `OciError` umbrella the module promises.

This change remediates every finding with strict-hexagonal solutions following the principle **ports contain only pure ABCs** — no shared adapter base classes live in ports. Instead:

- All pure-stdlib helpers move to `domain/` (JSON parsing, error matching, size parsing, tar building, list command building, prune parsing, encoding).
- Shared CLI orchestration patterns become proper helper ports: `ResultChecker` (for the result-checking pattern used in ~30 methods) and `ListExecutor[T]` (for the build-execute-check-parse list pattern).
- Each concrete parser, manager, and provider implements its port ABC directly, receiving collaborators via factory injection or calling domain helpers. No adapter inherits from a shared adapter base.

The v3 proposal's plan to move `BaseCliParser`, `CliBaseManager`, and `BaseCliRuntimeProvider` to `ports/` with implementation is replaced. Ports remain pure. The cost is ~120-140 lines of self-contained adapter code (each parser implements `is_not_found_error` and `parse_prune` as 3-line domain helper calls; each manager stores an injected `ResultChecker`/`ListExecutor`).

## What Changes

### Critical Bug Fixes (A series) — fixes unchanged, locations adjusted for pure design

- **A1**: `CliContainerManager.run()` honors `PortMapping.host_ip` — emits `-p <host_ip>:<host_port>:<container_port>/<protocol>` when `host_ip is not None`, `-p <host_port>:<container_port>/<protocol>` when `host_ip is None` and `host_port is not None`, `-p <host_ip>::<container_port>/<protocol>` when `host_ip is not None` and `host_port is None`, plain `-p <container_port>/<protocol>` when both are `None`. Validated by prototype covering all 4 combinations.
- **A2**: `parse_json_item` domain function gains scalar + length guard — rejects `int`/`str`/`bool`/`null`/`[]`/`[{},{}]` with `ParsingError`. Every parser calling `domain/json_parsing.parse_json_item()` automatically gets the fix.
- **A3**: `ProcessPipeReader.from_process()` becomes strict — raises `TypeError` if `process.stdout.fileno()` is unavailable. The `isinstance(fd, int)` defensive check and `fileobj.read()` fallback are deleted.
- **A4**: `CliResultChecker.check()` drops the dead `is_auth is not None` guard. When `ImagePullAccessDeniedError` is raised, `command`/`exit_code`/`stderr` are attached (A4 fix implemented in `CliResultChecker`).
- **A5**: `CliPtyTransport.execute_pty` raises `OciError` (not `ContainerRuntimeError`) when `command` is empty. Decouples transport from container concepts.
- **A6**: `CliImageManager.pull` raises `ImageRuntimeError` (the manager's `_generic_error` carried by its `ResultChecker`), not `ImageError`, when `parse_digest_from_pull` returns `""`; `command`/`exit_code`/`stderr` are attached.
- **A7**: `CliRuntime.version()` raises `OciError` (with `command`/`exit_code`/`stderr` attached) on any non-zero exit, not `RuntimeNotAvailableError`.
- **A8**: Delete the unused `Managers` port aggregate (`ports/aggregates.py`) and update `ARCHITECTURE.md` to remove the `create_managers` documentation drift.

### Hexagonal-Architecture Alignment (B series)

- **B1 (BREAKING, internal)**: Tighten `tests/architecture/test_layering.py`: the `adapters` layer's allowed-import set becomes `{"domain", "ports"}` only (was `{"domain", "ports", "adapters"}`). No shared adapter bases move to ports. Instead:
  - **Domain** gains 7 pure modules: `build_tar.py`, `size_parsing.py`, `json_parsing.py`, `error_matching.py`, `prune_parsing.py`, `list_command.py`, `encoding.py`, `result_checking.py`.
  - **Ports** gain 2 new pure ABC modules: `result_checker.py` (`ResultChecker`), `list_executor.py` (`ListExecutor[T]`). Plus `CompositeCancellationToken` + `compose_tokens` move to `ports/cancellation.py`.
  - **Adapters** gain 2 new helper modules: `helpers/result_checker.py` (`CliResultChecker`), `helpers/list_executor.py` (`CliListExecutor[T]`).
  - **`BaseCliParser` is deleted** — parsers implement port ABCs directly.
  - **`CliBaseManager` is deleted** — managers implement port ABCs directly, receive `ResultChecker` + `ListExecutor` via DI.
  - **`BaseCliRuntimeProvider` is deleted** — providers implement `RuntimeProvider` directly, receive parser classes from factory.
  - Result: 0 adapter→adapter imports (validated by prototype AST scan). ~21 existing import sites refactored.

- **B2**: Transports constructor signatures become strict:
  - `CliTransport(binary, binary_resolver, pipe_reader_factory)`
  - `CliStreamingTransport(binary, binary_resolver, pipe_reader_factory)`
  - `CliPtyTransport(binary_resolver, output_stream, pipe_reader_factory)`
  - No `or CliBinaryResolver()` fallback. No lazy `StdoutBufferStream` import.

- **B3**: Composition root no longer leaks manager types individually. `RuntimeFactoryConfig` gains `result_checker_factory` and `list_executor_factory` fields. The factory creates `CliResultChecker` and `CliListExecutor` instances per manager.

### Code Smells / Dead Code (C series)

- **C1**: The 4 copy-pasted `list()` methods are replaced with 1-line `self._list_executor.execute_list(...)` delegations. The dead `_execute_list` helper (never called) is deleted along with `CliBaseManager`.
- **C2**: Delete `_NOT_PROBED` sentinel in `adapters/binary.py`.
- **C3**: Tighten factory type signatures — `transport_factory: Callable[[str, BinaryResolver], Transport]` (second arg required, not `| None`).
- **C5**: Fix `_validate_tar_path` regex so `..foo` is not flagged as a parent reference.
- **C6**: `parse_size_to_bytes` accepts unitless integers and trailing whitespace.

### Test Fixes (D series)

- **D1/D6**: Rewrite wiring tests to assert correct `-p` forms with `host_ip` honored.
- **D2**: `test_parsers_is_frozen_dataclass` uses correct parser types per slot.
- **D3**: `test_factory_config_defaults_are_none` asserts all 12+ fields.
- **D4**: Fix broken `"docker --version"` dict key to `("docker", "--version")`.
- **D5**: Drop dead `@patch("subprocess.run")` decorators.
- **D7**: Replace `assert isinstance(runtime.images, CliImageManager)` with `assert isinstance(runtime.images, ImageManager)`.
- **D8 (new)**: New contract test `test_result_checker_requires_error_types` verifies `CliResultChecker` cannot be instantiated without `generic_error` and `not_found_error`. New contract test `test_list_executor_parse_list_callable` verifies `CliListExecutor` calls `parse_list` with decoded stdout.
- **D9**: Add fixture warning for missing conformance fixtures.
- **D10**: Drop `_safe_int` where redundant.

### Documentation Drift (E series)

- **E1**: Update `ARCHITECTURE.md` routing matrix — `detach=True → streaming.stream() (no callbacks)`.
- **E2**: Note scalar-guard covers both JSON parsing functions.
- **E3**: Drop stale "subprocess.run" reference in `ports/streaming.py`.
- **E4 (subsumed by A8)**: Remove `create_managers` block from ARCHITECTURE.md.
- **E5**: Unify timeout types across `ports/managers.py` — all `float | None`.
- **E6**: Architecture linter target documented as `adapter → {domain, ports}`.

### Minor (F series)

- `CliRuntime.version()` propagates `OperationTimeoutError`.
- `CliRuntimeDiscovery.available()` drops dead `except` clause.
- `RuntimeFactory.create()` raises `ProviderNotRegisteredError(OciError)`.
- `CliContainerManager.run()` honors `--network bridge` when explicitly requested; emits log-driver warning when unsupported.

## Capabilities

### New Capabilities

- `oci-result-checker-port`: `ResultChecker` port + `CliResultChecker` adapter. The check-result pattern used by ~30 manager methods is extracted to a proper port with a pure ABC. The adapter receives error types and detection callables via constructor injection.
- `oci-list-executor-port`: `ListExecutor[T]` port + `CliListExecutor[T]` adapter. The build-execute-check-parse list pattern is extracted to a generic port. Each manager's `list()` delegates to a type-specific executor.
- `oci-port-binding-strictness`: `PortMapping.host_ip` honored end-to-end.
- `oci-pipe-reader-port`: `PipeReader` port abstracts fd-based subprocess output reading.
- `oci-version-error-contract`: `ContainerEngine.version()` raises `OciError` on non-zero exit.
- `oci-doc-cleanup-v3`: Documentation drift removed.

### Modified Capabilities

- `oci-strict-hexagonal-layering`: Now achieves zero adapter→adapter imports without placing shared implementation in ports. Pure helpers in `domain/`. Helper ports (`ResultChecker`, `ListExecutor`) with pure ABCs.
- `oci-exception-typing`: A4 simplified via `ResultChecker`. A5 `OciError` for empty PTY command. A6 `ImageRuntimeError` for digest failure. New `ProviderNotRegisteredError`.
- `oci-parser-real-cli-conformance`: Scalar rejection in `domain/json_parsing.py`. Conformance tests verify each self-contained parser.
- `oci-test-contracts`: Wiring tests assert against ports. `ResultChecker`/`ListExecutor` constructor contract tests.
- `oci-pull-contract`: `ImageRuntimeError` with context on digest failure.
- `oci-build-flag-completeness`: All `list()` delegate to `ListExecutor`.

## Impact

- **Adapter surface (BREAKING, internal)**: All 4 manager classes change constructor signatures (gain `result_checker` and `list_executor`). All 4 provider classes change construction (receive parser classes). 8 parser classes lose `BaseCliParser` inheritance. ~40 test sites updated.
- **Port surface**: 2 new port modules (`result_checker`, `list_executor`). `ports/cancellation.py` gains `CompositeCancellationToken` + `compose_tokens`.
- **Domain surface**: 7 new modules (all pure stdlib). Domain purity preserved.
- **Factory surface**: `RuntimeFactoryConfig` gains `result_checker_factory` and `list_executor_factory`. Factory wiring grows to create per-manager instances.
- **Test surface**: ~50 tests edited/added. New contract tests for `ResultChecker` and `ListExecutor`.
- **Docs**: ARCHITECTURE.md edits (share bases section removed, new port/helper descriptions, remediation log).
- **Dependencies**: None. Stdlib only.
- **Performance**: Negligible — one extra callable dispatch per list operation; one extra object allocation per check call.
- **Risk**: T2 (parser rewiring) is the largest mechanical change — 8 parsers lose `BaseCliParser` inheritance. Mitigated by phased commits with green tests after each phase and the architecture linter as the regression gate.
