## Why

A full audit of the `oci-runtime` module found 3 critical bugs (Podman pull digest extraction, Podman null `RepoTags` handling, `stream_output` silently discarding output), 5 high-severity issues (timeout enforcement gap in `process.wait()`, broken factory type contract, untested/incorrect auth-error classification, Podman missing auth-error patterns, critical error-path coverage gaps), and 18 medium/low issues spanning hexagonal-architecture drift, type incongruences, dead code, documentation drift, and non-meaningful tests. All 826 tests pass, yet several critical code paths are never exercised and two Podman bugs produce runtime crashes on real CLI output. This change remediates every finding with evidence-backed, hexagonal-architecture-aligned solutions validated by throwaway prototypes.

## What Changes

### Critical Bug Fixes
- **C1**: Rewrite `PodmanImageParser.parse_digest_from_pull` to eliminate premature `return ""` — scan all lines, skip noise prefixes, never exit early on non-matching lines. Backed by evidence from Podman docs/source: progress on stderr, bare hex ID on stdout.
- **C2**: Fix `PodmanImageParser.parse_inspect` null `RepoTags` — use `item.get("RepoTags") or []` (matching Docker parser). Evidence: Docker returns `null`, Podman returns `[]` for untagged images; both must be handled.
- **C3**: Fix `stream_output=True` discarding output — wire `on_stdout`/`on_stderr` callbacks that write to the container manager's `OutputStream`, consistent with PTY routing. Validated by prototype.

### High-Severity Fixes
- **H1**: Add timeout-aware poll loop after `ProcessPipeReader.read()` in all three transports — `process.wait(timeout=0.5)` in a loop checking `effective_token.is_cancelled`, using the Python-documented "safe to retry" pattern. Validated by prototype against a process that closes pipes but stays alive.
- **H2**: Fix `RuntimeFactoryConfig` type annotations — `Callable[[str], Transport]` → `Callable[[str, BinaryResolver], Transport]` (matching call sites, default factories, and ARCHITECTURE.md). Validated by prototype.
- **H3**: Add `ImagePullAccessDeniedError` raising-path test with real `DockerImageParser`; fix `test_pull_nonexistent_image` workflow test that asserts the wrong exception via `MockImageParser`.
- **H4**: Add Podman-specific `_auth_error_patterns` — `"authentication required"`, `"requested access to the resource is denied"` (evidence: Podman/containers/image source, NOT Docker's "pull access denied").
- **H5**: Add tests for: `CliTransport` timeout→`OperationTimeoutError`, `CliTransport` cancellation→`returncode=-1`, PTY stderr separation with real `ProcessPipeReader`, tar path-traversal prevention, `logs(follow=True)` finally error propagation.

### Medium-Severity Fixes
- **M1**: Add `ValueError` to `CliTransport` stdin-thread `except` clause (race with `BufferedWriter` close).
- **M2**: Remove `fd < 1000` magic number from `ProcessPipeReader._read_fd` — use `isinstance(fd, int)` alone. Validated by prototype.
- **M3**: Fix `CliStreamingTransport` cancellation order — kill process before joining stdin thread.
- **M4**: Fix `logs(follow=True)` thread leak — add `GeneratorExit` guard in `finally` error propagation.
- **M5**: Fix build output error contract — `build()` wraps `ParsingError` from `parse_build_output` in `ImageRuntimeError(from e)`, removing dead `if not ident` guard. Validated by prototype. Aligns with `oci-test-contracts` spec.

### Hexagonal Architecture
- **A1**: Move manager construction from `BaseCliRuntimeProvider.create_managers()` into `RuntimeFactory`. Remove `create_managers` from `RuntimeProvider` port. Provider retains `kind`, `capabilities`, `create_parsers` only. Factory becomes sole composition root for manager/transport/engine adapters. Validated by design analysis.
- **A2**: Deep-freeze domain types — `dict` fields → `MappingProxyType`, `list` fields → `tuple`, via `object.__setattr__` in `__post_init__` with shared `_freeze_mapping`/`_freeze_sequence` helpers. Validated by prototype.

### Type & API Incongruences
- **T1**: Unify `timeout` type to `float | None` across `Transport.execute`, `StreamingTransport.stream`, and all manager methods.
- **T2**: Fix `RuntimePreference` docstring (does NOT probe availability; factory.create() doesn't probe either).
- **T3**: Fix `ARCHITECTURE.md` `RuntimeProvider.create_managers` signature (was showing Optional defaults; port requires them). Superseded by A1 (method removed).

### Documentation & Spec Reconciliation
- **D1**: Update active specs `oci-pull-contract`, `oci-parser-real-cli-conformance` to use `parse_digest_from_pull` (not `parse_id_from_pull`). Update `oci-pty-timeout` to use `execute_pty` (not `run_pty`). Fix `ports/output_stream.py` docstring.
- **D2**: Correct false archived-change claims (RuntimeCapabilities location, ports/__init__ re-export, _not_found_error default).
- **D3**: Rename `test_prune_returns_dict` → `test_prune_returns_prune_result` across contract test files.

### Test Quality
- **Q1**: Replace GIL-dependent concurrency tests with real shared-state tests or remove misleading ones.
- **Q2**: Fix build-command canned-response keys in tests (flags-before-positional is the actual emitted order).
- **Q3**: Fix misnamed/duplicate tests (`test_stream_selectors_cleaned_up`, `test_select_raises_value_error`, `test_check_result_lacks_is_not_found_error_raises_attribute_error`).
- **Q4**: Replace `sys.stdout.buffer` patching in PTY test with `OutputStream` injection.
- **Q5**: Replace `time.sleep`-based `DeadlineCancellationToken` tests with deterministic timer verification.
- **Q6**: Fix fake parsers in `test_provider.py` to return `PruneResult` (not `dict`).

## Capabilities

### New Capabilities
- `oci-domain-deep-immutability`: Deep immutability enforcement for all domain value objects — `MappingProxyType` for dict fields, `tuple` for list fields, `object.__setattr__` in `__post_init__`.
- `oci-composition-root-consolidation`: Factory as sole composition root — manager construction moves from provider to factory; `RuntimeProvider.create_managers` removed from port.
- `oci-stream-output-contract`: `stream_output=True` routes output through `OutputStream` callbacks, consistent with PTY mode.
- `oci-timeout-enforcement-completeness`: All transports enforce timeout through the full process lifecycle — poll-loop `process.wait(timeout=...)` after pipe drain, not just inside the reader loop.
- `oci-podman-parser-parity`: Podman parsers achieve full parity with Docker parsers — `RepoTags` null handling, auth-error patterns, digest extraction robustness.
- `oci-build-error-contract`: `build()` raises `ImageError` (via `ImageRuntimeError`) for unparseable output, wrapping `ParsingError` as `__cause__`.
- `oci-factory-type-contract`: `RuntimeFactoryConfig` callable annotations match actual call-site signatures.
- `oci-test-fidelity`: Tests exercise real error paths with real parsers, realistic fixtures, and deterministic assertions — no mock-pass-through giving false confidence.

### Modified Capabilities
- `oci-pull-contract`: Update method name from `parse_id_from_pull` to `parse_digest_from_pull`; add Podman auth-error pattern requirements.
- `oci-parser-real-cli-conformance`: Update method name from `parse_id_from_pull` to `parse_digest_from_pull`; add null `RepoTags` handling requirement for both runtimes.
- `oci-pty-timeout`: Update method name from `run_pty` to `execute_pty`; add `CliTransport.execute()` timeout requirement.
- `oci-test-contracts`: Update `test_build_empty_output` to assert `ImageError` (not `ParsingError`); add auth-error raising-path test requirement; add tar path-traversal test requirement.
- `oci-exception-typing`: Add `build()` exception wrapping rule (`ParsingError` → `ImageRuntimeError`).

## Impact

- **Source files modified**: `domain/types.py`, `domain/exceptions.py` (no), `ports/provider.py`, `ports/transport.py`, `ports/streaming.py`, `ports/managers.py`, `factory.py`, `adapters/parser/podman.py`, `adapters/parser/docker.py` (no), `adapters/parser/base.py` (no), `adapters/managers/container.py`, `adapters/managers/image.py`, `adapters/managers/base.py` (no), `adapters/transport/cli.py`, `adapters/transport/streaming.py`, `adapters/transport/pty.py`, `adapters/_process_reader.py`, `adapters/provider/_base.py`, `adapters/provider/docker.py`, `adapters/provider/podman.py`, `adapters/_cancellation.py` (no), `__init__.py` (if exports change), `ports/output_stream.py` (docstring).
- **Test files modified**: ~20 test files across `unit/`, `conformance/`, `audit/`, `boundary/`, `ports/`, `contract/`, `wiring/`.
- **Spec files modified**: 5 existing specs updated; 8 new spec deltas created.
- **Documentation**: `ARCHITECTURE.md` updated for composition root, immutability, stream_output, timeout enforcement, method names.
- **BREAKING**: `RuntimeProvider.create_managers()` removed from port (A1). `RuntimeFactoryConfig` callable signatures changed (H2). Domain types now return `tuple`/`MappingProxyType` instead of `list`/`dict` (A2) — callers that mutate these fields will break. `build()` now raises `ImageRuntimeError` instead of `ParsingError` for invalid output (M5).
- **Dependencies**: None added (zero-dependency constraint preserved).
- **Python version**: 3.12+ (no change).
