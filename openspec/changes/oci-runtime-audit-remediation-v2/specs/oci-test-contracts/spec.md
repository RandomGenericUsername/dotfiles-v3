## MODIFIED Requirements

### Requirement: B5 wiring tests must assert injected instances

The factory wiring tests for `tty_detector_factory` and `output_stream_factory` must assert that the injected instances are actually wired into the container manager, not that `engine.capabilities is not None` (a tautology that is always true). The test must verify `engine.containers._tty_detector` is the injected `FakeTtyDetector` instance and `engine.containers._output_stream` is the injected `BytesIO` instance.

#### Scenario: Custom TTY detector factory is used
- **WHEN** `RuntimeFactoryConfig(tty_detector_factory=lambda: custom_tty)` is passed to the factory
- **THEN** `engine.containers._tty_detector` is `custom_tty` (the same instance), not the default `StdoutTtyDetector`

#### Scenario: Custom output stream factory is used
- **WHEN** `RuntimeFactoryConfig(output_stream_factory=lambda: custom_stream)` is passed to the factory
- **THEN** `engine.containers._output_stream` is `custom_stream` (the same instance), not the default `StdoutBufferStream`

### Requirement: test_build_empty_output must assert ImageError

The boundary test `test_build_empty_output` must assert that `build()` raises `ImageError` (or subclass `ImageRuntimeError`) when the build output cannot be parsed to extract an image id. `build()` must wrap `ParsingError` from `parse_build_output` in `ImageRuntimeError(from e)`, so the raised exception is an `ImageError` subclass, not a `ParsingError`.

#### Scenario: Build with empty output raises ImageError
- **WHEN** `docker build` returns exit code 0 with empty stdout
- **THEN** `build()` raises `ImageError` (or subclass `ImageRuntimeError`), and `except ImageError` catches it. The `ParsingError` is preserved as `__cause__`.

## ADDED Requirements

### Requirement: Auth-error raising path tested with real parser

The `ImagePullAccessDeniedError` raising path through `CliImageManager._check_result` must be tested with the real `DockerImageParser` (not `MockImageParser`). The test injects `"pull access denied"` stderr and asserts `ImagePullAccessDeniedError`, not `ImageNotFoundError`.

#### Scenario: Pull access denied raises ImagePullAccessDeniedError
- **WHEN** `CliImageManager.pull()` is called with a transport that returns stderr `"pull access denied for img"` and the real `DockerImageParser`
- **THEN** `ImagePullAccessDeniedError` is raised (not `ImageNotFoundError`)

### Requirement: Tar path-traversal prevention tested

`create_build_tar()` must be tested with invalid paths (absolute paths, `..` parent references) to verify the `_validate_tar_path` guard raises `ValueError`.

#### Scenario: Absolute path in tar rejected
- **WHEN** `create_build_tar()` is called with `files={"/etc/passwd": b"data"}`
- **THEN** `ValueError` is raised

#### Scenario: Parent traversal in tar rejected
- **WHEN** `create_build_tar()` is called with `files={"../secret": b"data"}`
- **THEN** `ValueError` is raised

### Requirement: logs follow error propagation tested

`CliContainerManager.logs(follow=True)` must be tested to verify that errors from the streaming transport are re-raised from the generator's `finally` block, even when the consumer breaks early. `GeneratorExit` must not mask real errors.

#### Scenario: Streaming error re-raised on early break
- **WHEN** `logs(container, follow=True)` is iterated and the consumer breaks after the first chunk, and the streaming transport raised an error
- **THEN** the error is re-raised from the `finally` block (not silently swallowed)
