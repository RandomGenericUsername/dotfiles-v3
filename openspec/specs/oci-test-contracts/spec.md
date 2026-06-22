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

The boundary test `test_build_empty_output` must assert that `build()` raises `ImageError` when the build output cannot be parsed to extract an image id, not that it returns `"sha256:"` (which codifies the silent-failure bug as expected behavior). This aligns `build()` with `pull()`'s A5 fix.

#### Scenario: Build with empty output raises ImageError
- **WHEN** `docker build` returns exit code 0 with empty stdout
- **THEN** `build()` raises `ImageError` (or the parser returns empty and the manager raises), not `result == "sha256:"`
