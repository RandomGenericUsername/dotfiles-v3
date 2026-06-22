## 1. Critical Bug Fixes (Non-Breaking)

- [x] 1.1 Fix `PodmanImageParser.parse_digest_from_pull` — remove premature `return ""`, scan all lines in reverse with noise-prefix skip tuple (`Resolved`, `Trying`, `Getting`, `Copying`, `Writing`, `Storing`), `continue` on non-matching lines, only `return ""` after exhausting all lines. (D-C1, C1)
- [x] 1.2 Fix `PodmanImageParser.parse_inspect` null `RepoTags` — change `tags=item.get("RepoTags", [])` to `tags=(item.get("RepoTags") or [])` at `podman.py:143`. (D-C2, C2)
- [x] 1.3 Fix `PodmanImageParser` missing `_auth_error_patterns` — add `("authentication required", "requested access to the resource is denied")` class attribute. (D-H4, H4)
- [x] 1.4 Fix `ProcessPipeReader._read_fd` — remove `and fd < 1000` from the `isinstance(fd, int)` check at `_process_reader.py:36`. (D-M2, M2)
- [x] 1.5 Fix `CliTransport` stdin thread — add `ValueError` to the `except` clause at `cli.py:53` (`except (OSError, ValueError):`). (D-M1, M1)
- [x] 1.6 Fix `CliStreamingTransport` cancellation order — move `process.kill()` + `process.wait()` BEFORE `_stdin_thread.join(timeout=5)` in the cancellation branch at `streaming.py:71-76`. (D-M3, M3)
- [x] 1.7 Fix `logs(follow=True)` error propagation — guard `if errors and not isinstance(errors[0], GeneratorExit):` in the `finally` block at `container.py:273-274`. (D-M4, M4)
- [x] 1.8 Run test suite to verify no regressions from Phase 1 fixes.

## 2. High-Severity Fixes (Timeout & Factory Types)

- [x] 2.1 Add timeout-aware poll loop to `CliTransport.execute()` — replace bare `process.wait()` at `cli.py:76` with `while True: if effective_token.is_cancelled: kill+wait+raise/return; try: process.wait(timeout=0.5); break; except TimeoutExpired: continue`. (D-H1, H1)
- [x] 2.2 Add timeout-aware poll loop to `CliStreamingTransport.stream()` — same pattern at `streaming.py:86`. (D-H1, H1)
- [x] 2.3 Add timeout-aware poll loop to `CliPtyTransport.execute_pty()` — same pattern at `pty.py:79`. (D-H1, H1)
- [x] 2.4 Fix `RuntimeFactoryConfig` type annotations — `transport_factory: Callable[[str, BinaryResolver], Transport]` and `streaming_transport_factory: Callable[[str, BinaryResolver], StreamingTransport]` at `factory.py:31-32`. (D-H2, H2)
- [x] 2.5 Unify `timeout` type to `float | None` — change `Transport.execute()` (`ports/transport.py:13`) and `StreamingTransport.stream()` (`ports/streaming.py:20`) from `int | None` to `float | None`. (D-T1, T1)
- [x] 2.6 Fix `RuntimePreference` docstring — update to state that creation does NOT probe availability. (D-T2, T2)
- [x] 2.7 Run test suite to verify no regressions from Phase 2 fixes.

## 3. Build Error Contract (Breaking — Phase 3a)

- [x] 3.1 Wrap `parse_build_output` in `CliImageManager.build()` with `try/except ParsingError → raise ImageRuntimeError(...) from e`. Remove dead `if not ident or ident == "sha256:":` guard at `image.py:67-71`. (D-M5, M5)
- [x] 3.2 Update `test_build_empty_output` in `tests/unit/boundary/test_empty_outputs.py` to assert `ImageError` (or `ImageRuntimeError`) instead of `ParsingError`. (D-M5, M5)
- [x] 3.3 Add test: `build()` with invalid hex output raises `ImageRuntimeError` with `__cause__` as `ParsingError`. (D-M5, M5)
- [x] 3.4 Run test suite to verify build error contract fix.

## 4. stream_output Fix (Breaking — Phase 3b)

- [x] 4.1 Fix `CliContainerManager.run()` stream_output path — when `config.stream_output=True` and not TTY, call `self._streaming.stream()` with `on_stdout`/`on_stderr` callbacks that write to `self._output_stream`. Return `""`. (D-C3, C3)
- [x] 4.2 Add test: `stream_output=True` writes chunks to `OutputStream` and returns `""`. (D-C3, C3)
- [x] 4.3 Add test: `stream_output=True` with `_output_stream=None` does not crash. (D-C3, C3)
- [x] 4.4 Add test: `stream_output=False` returns stdout string (regression guard). (D-C3, C3)
- [x] 4.5 Run test suite to verify stream_output fix.

## 5. Composition Root Consolidation (Breaking — Phase 3c)

- [x] 5.1 Add `container_manager_cls`, `image_manager_cls`, `volume_manager_cls`, `network_manager_cls` fields to `RuntimeFactoryConfig` (defaulting to `None`, resolved lazily). (D-A1, A1)
- [x] 5.2 Add `_default_*_manager_cls` lazy resolution helpers in `factory.py` (importing `CliContainerManager`, `CliImageManager`, `CliVolumeManager`, `CliNetworkManager`). (D-A1, A1)
- [x] 5.3 Move manager instantiation into `RuntimeFactory.create()` — after `provider.create_parsers()`, instantiate the four managers using the config-resolved classes. Wire `CliContainerManager` with `streaming`, `tty_detector`, `pty_transport`, `cancellation_factory`, `output_stream`. (D-A1, A1)
- [x] 5.4 Remove `create_managers` from `RuntimeProvider` ABC (`ports/provider.py`). Remove all `PtyTransport`, `OutputStream`, `TtyDetector`, `CancellationToken`, `StreamingTransport`, `Transport` imports from `ports/provider.py`. (D-A1, A1)
- [x] 5.5 Remove `create_managers` from `BaseCliRuntimeProvider` (`adapters/provider/_base.py`). Remove `Cli*Manager` imports from `_base.py`. (D-A1, A1)
- [x] 5.6 Update `DockerRuntimeProvider` and `PodmanRuntimeProvider` — remove any `create_managers` override (none exist, but verify). (D-A1, A1)
- [x] 5.7 Update `tests/unit/ports/test_provider.py` — remove `create_managers` from the test provider; update fake provider to only implement `kind`, `capabilities`, `create_parsers`. Fix fake parsers to return `PruneResult` (not `dict`). (D-A1, A1, Q6)
- [x] 5.8 Update `tests/unit/adapters/test_providers.py` — adjust for the new provider interface. (D-A1, A1)
- [x] 5.9 Update `tests/unit/wiring/test_factory_wiring.py` — adjust for factory building managers directly. (D-A1, A1)
- [x] 5.10 Run test suite to verify composition root consolidation.

## 6. Deep Immutability (Breaking — Phase 3d)

- [x] 6.1 Add `_freeze_mapping(self, field_names)` and `_freeze_sequence(self, field_names)` module-level helpers in `domain/types.py` using `object.__setattr__` + `MappingProxyType` / `tuple()`. (D-A2, A2)
- [x] 6.2 Update `BuildContext.__post_init__` — call `_freeze_mapping(self, ["files", "build_args", "labels", "build_contexts"])`. (D-A2, A2)
- [x] 6.3 Update `RunConfig.__post_init__` — call `_freeze_mapping(self, ["environment", "labels"])` and `_freeze_sequence(self, ["volumes", "ports", "runtime_flags"])`. Change `command` annotation to `tuple[str, ...] | None` and convert in `__post_init__` (None stays None). (D-A2, A2)
- [x] 6.4 Add `__post_init__` to `ImageInfo` — call `_freeze_mapping(self, ["labels"])` and `_freeze_sequence(self, ["tags"])`. (D-A2, A2)
- [x] 6.5 Add `__post_init__` to `ContainerInfo` — call `_freeze_mapping(self, ["labels"])` and `_freeze_sequence(self, ["ports"])`. (D-A2, A2)
- [x] 6.6 Add `__post_init__` to `VolumeInfo` — call `_freeze_mapping(self, ["labels"])`. (D-A2, A2)
- [x] 6.7 Add `__post_init__` to `NetworkInfo` — call `_freeze_mapping(self, ["labels"])`. (D-A2, A2)
- [x] 6.8 Update field type annotations: `dict[...]` → `Mapping[...]` (from `collections.abc`), `list[...]` → `tuple[...]`, `field(default_factory=dict)` → `field(default_factory=lambda: MappingProxyType({}))` or keep `dict` default and convert in `__post_init__`. (D-A2, A2)
- [x] 6.9 Update `tests/unit/domain/test_types.py` — change `== [...]` assertions to `== (...)` for list fields (~6 assertions). Add deep-immutability regression tests: mutation raises `TypeError`, `isinstance(field, tuple)`, `isinstance(field, MappingProxyType)`. (D-A2, A2)
- [x] 6.10 Update `tests/unit/ports/test_capabilities.py` if needed (already uses tuple, should pass). (D-A2, A2)
- [x] 6.11 Run test suite to verify deep immutability.

## 7. Test Fidelity (Phase 4)

- [x] 7.1 Add test: `CliTransport.execute()` timeout raises `OperationTimeoutError` (use a process that hangs with `timeout=0.1`). (H5, H1)
- [x] 7.2 Add test: `CliTransport.execute()` with pre-cancelled token returns `returncode=-1`. (H5, H1)
- [x] 7.3 Add test: PTY stderr separation — use a process that writes to both stdout and stderr, verify `RawExecResult.stdout` and `RawExecResult.stderr` are separate. (H5)
- [x] 7.4 Add test: tar path-traversal prevention — `create_build_tar()` with absolute path and `..` path raises `ValueError`. (H5)
- [x] 7.5 Add test: `logs(follow=True)` error propagation in `finally` — streaming error re-raised even when consumer breaks early. (H5)
- [x] 7.6 Add test: `ImagePullAccessDeniedError` raising path with real `DockerImageParser` — inject `"pull access denied"` stderr, assert `ImagePullAccessDeniedError`. (H3)
- [x] 7.7 Fix `test_pull_nonexistent_image` in `tests/unit/wiring/test_workflows.py` — either use real parser and assert `ImagePullAccessDeniedError`, or fix `MockImageParser.is_not_found_error` to return `False` for `"pull access denied"`. (H3)
- [x] 7.8 Fix build-command canned-response keys in `test_image_manager_contract.py`, `test_workflows.py`, `test_malformed_output.py` — change `("-", "--quiet")` to `("--quiet", "-")`. (Q2)
- [x] 7.9 Remove misleading concurrency tests (`test_concurrent_manager_calls`, `test_recording_transport_thread_safety`) or replace with real shared-state tests. Keep `test_concurrent_factory_create` with updated docstring. (Q1)
- [x] 7.10 Fix `test_stream_selectors_cleaned_up` — either verify `selector.close()` is called or rename to match what it tests (exception propagation). (Q3)
- [x] 7.11 Fix `test_select_raises_value_error` — rename to `test_reader_raises_value_error` or similar. (Q3)
- [x] 7.12 Remove `test_check_result_lacks_is_not_found_error_raises_attribute_error` — tests Python language guarantee, not application behavior. (Q3)
- [x] 7.13 Replace `sys.stdout.buffer` patching in `test_run_pty_default_writes_to_stdout` with `OutputStream` injection. (Q4)
- [x] 7.14 Replace `time.sleep`-based `DeadlineCancellationToken` tests with deterministic verification (mock timer or direct cancel→is_cancelled test). (Q5)
- [x] 7.15 Fix fake parsers in `test_provider.py` to return `PruneResult` (not `dict`). (Q6)
- [x] 7.16 Rename `test_prune_returns_dict` → `test_prune_returns_prune_result` across all contract test files. (D3)
- [x] 7.17 Run full test suite to verify all test fidelity changes.

## 8. Documentation & Spec Reconciliation

- [x] 8.1 Update `ARCHITECTURE.md:85` — "The factory is the composition root: it is the only place manager, transport, engine, discovery, and infrastructure adapter classes are referenced. Provider subclasses reference only parser adapter classes." (D-A1)
- [x] 8.2 Update `ARCHITECTURE.md:93` — "All domain value objects use `frozen=True` AND hold only immutable containers (`tuple`, `MappingProxyType`), so instances are deeply immutable." (D-A2)
- [x] 8.3 Update `ARCHITECTURE.md` — add `stream_output` routing matrix (detach/TTY/stream_output/neither). (D-C3)
- [x] 8.4 Update `ARCHITECTURE.md` — document the timeout-aware poll loop pattern for all three transports. (D-H1)
- [x] 8.5 Update `ARCHITECTURE.md:192` — verify `parse_digest_from_pull` is documented (already done). (D1)
- [x] 8.6 Update `ARCHITECTURE.md:135,149,171` — verify `execute_pty` is documented (already done). (D1)
- [x] 8.7 Fix `ports/output_stream.py` docstring — replace `run_pty` with `execute_pty`. (D1)
- [x] 8.8 Update `ARCHITECTURE.md` "Adding a New Runtime" section — provider now only needs `kind`, `capabilities`, `create_parsers`; no `create_managers`. (D-A1)
- [x] 8.9 Update `ARCHITECTURE.md:344-357` — remove `create_managers` signature from the port documentation. (D-A1, T3)
- [x] 8.10 Update `ARCHITECTURE.md` Remediation Log — add entry for this change. (D2)
- [x] 8.11 Fix `ports/__init__.py` if any re-exports change due to composition root consolidation. (D-A1)
- [x] 8.12 Run `ruff check src/` and `ruff format --check src/` to verify no lint/format issues.
- [x] 8.13 Run full test suite (`uv run pytest tests/ -v`) to verify all 826+ tests pass.
- [x] 8.14 Run architecture linter (`tests/architecture/test_layering.py`) to verify import-direction rules still pass.

## 9. Final Verification

- [x] 9.1 Verify all audit findings are addressed — cross-reference each C1-C3, H1-H5, M1-M5, A1-A2, T1-T3, D1-D3, Q1-Q6 item against the implemented changes.
- [x] 9.2 Verify no new dependencies added (`pyproject.toml` `dependencies = []` unchanged).
- [x] 9.3 Verify Python 3.12+ compatibility (no 3.13+ features used).
- [x] 9.4 Verify `__all__` in `oci_runtime/__init__.py` is unchanged (no new public exports).
- [x] 9.5 Run `make check` (lint + format-check + test) for final sign-off.
