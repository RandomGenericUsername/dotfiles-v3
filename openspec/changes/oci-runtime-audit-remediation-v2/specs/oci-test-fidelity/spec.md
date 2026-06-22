## ADDED Requirements

### Requirement: Tests exercise real error paths with real parsers

Manager-level error-path tests SHALL use real parser implementations (not `MockImageParser` or other mock parsers) when verifying error classification. Mock parsers that return hardcoded `True`/`False` for `is_not_found_error`/`is_auth_error` give false confidence by asserting the wrong exception type for real CLI output.

#### Scenario: ImagePullAccessDeniedError raising path tested with real parser
- **WHEN** `CliImageManager.pull()` is tested with stderr `"pull access denied for img"` and the real `DockerImageParser`
- **THEN** the test asserts `ImagePullAccessDeniedError` is raised (not `ImageNotFoundError`), matching the real parser's `is_auth_error` → `True` / `is_not_found_error` → `False` classification

#### Scenario: Workflow test pull-access-denied uses correct exception type
- **WHEN** `test_pull_nonexistent_image` injects `"pull access denied"` stderr
- **THEN** the test asserts `ImagePullAccessDeniedError` (if using real parser) or the mock parser's `is_not_found_error` returns `False` for `"pull access denied"` (if using mock)

### Requirement: Critical transport error paths are tested

`CliTransport.execute()` timeout and cancellation behavior SHALL be tested. PTY stderr separation SHALL be tested with a real `ProcessPipeReader` (not fully mocked). Tar path-traversal prevention SHALL be tested. `logs(follow=True)` error propagation in `finally` SHALL be tested.

#### Scenario: CliTransport timeout raises OperationTimeoutError
- **WHEN** `CliTransport.execute(["sleep", "30"], timeout=0.1)` is tested
- **THEN** the test asserts `OperationTimeoutError` is raised (not `subprocess.TimeoutExpired`)

#### Scenario: CliTransport cancellation returns returncode=-1
- **WHEN** `CliTransport.execute(cmd, cancel_token=pre_cancelled_token)` is tested
- **THEN** the test asserts `result.returncode == -1`

#### Scenario: PTY stderr separation verified
- **WHEN** `CliPtyTransport.execute_pty()` is tested with a process that writes to both stdout and stderr
- **THEN** the test asserts stdout data and stderr data are in separate fields of `RawExecResult` (stdout via PTY master, stderr via pipe)

#### Scenario: Tar path traversal rejected
- **WHEN** `create_build_tar()` is called with a file path containing `..` or an absolute path
- **THEN** `ValueError` is raised

#### Scenario: logs follow error propagation
- **WHEN** `logs(container, follow=True)` is called and the streaming transport raises an error, and the consumer breaks early
- **THEN** the error is re-raised from the generator's `finally` block (not silently swallowed)

### Requirement: Test canned responses match actual command shapes

Test `RecordingTransport` response keys SHALL match the actual command shape emitted by the adapter. Build-command response keys SHALL have flags before the positional arg (e.g. `("docker", "build", "-t", "img", "--quiet", "-")`), matching `CliImageManager.build()`'s `default_build_flags` before `positional`.

#### Scenario: Build command response key matches emitted order
- **WHEN** a test sets a `RecordingTransport` response for a build command
- **THEN** the key tuple has `--quiet` before `-` (the positional), matching `image.py:44` emit order

### Requirement: Tests do not rely on GIL atomicity for concurrency claims

Concurrency tests SHALL either test real concurrent shared-state access with verifiable thread-safety properties, or be removed if the component is not designed to be thread-safe. Tests that pass only because of CPython GIL atomicity give false confidence.

#### Scenario: Concurrency test verifies a real property
- **WHEN** a concurrency test runs
- **THEN** it tests a property that would fail without synchronization (not GIL-dependent list append atomicity)

### Requirement: Test names match test behavior

Test names SHALL accurately describe what the test verifies. Misnamed tests (e.g. `test_stream_selectors_cleaned_up` that doesn't check `selector.close()`, `test_prune_returns_dict` that asserts `PruneResult`) SHALL be renamed or fixed.

#### Scenario: Prune test name matches assertion
- **WHEN** a prune contract test runs
- **THEN** the test name contains "prune_result" (not "dict"), matching the `PruneResult` assertion

### Requirement: Fake parsers in tests conform to port return types

Test fake/mock parsers SHALL return the correct types specified by the port contract. `parse_prune()` SHALL return `PruneResult`, not `dict`.

#### Scenario: Fake parser parse_prune returns PruneResult
- **WHEN** a fake parser's `parse_prune()` is called in a test
- **THEN** it returns a `PruneResult` instance, not a `dict`
