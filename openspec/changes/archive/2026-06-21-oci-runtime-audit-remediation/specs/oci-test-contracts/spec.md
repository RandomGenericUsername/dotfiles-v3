## ADDED Requirements

### Requirement: Mock parsers conform to port return types
Every test parser (in `tests/helpers/mock_parsers.py` and any local `_MockParser` class in test files) SHALL implement `parse_prune` returning a `PruneResult` instance, matching the port declaration `-> PruneResult`. Test parsers MUST NOT return `dict[str, int]`.

#### Scenario: MockContainerParser.parse_prune returns PruneResult
- **WHEN** `MockContainerParser().parse_prune("")` is called
- **THEN** the result `isinstance(result, PruneResult)` is `True`

#### Scenario: MockImageParser.parse_prune returns PruneResult
- **WHEN** `MockImageParser().parse_prune("")` is called
- **THEN** the result `isinstance(result, PruneResult)` is `True`

#### Scenario: MockVolumeParser.parse_prune returns PruneResult
- **WHEN** `MockVolumeParser().parse_prune("")` is called
- **THEN** the result `isinstance(result, PruneResult)` is `True`

#### Scenario: MockNetworkParser.parse_prune returns PruneResult
- **WHEN** `MockNetworkParser().parse_prune("")` is called
- **THEN** the result `isinstance(result, PruneResult)` is `True`

### Requirement: Port-test fakes conform to port signatures
Test fakes defined inside `tests/unit/ports/` SHALL use the exact signatures declared by the port ABCs. In particular, `parse_prune` return type SHALL be `PruneResult`, and `Transport.execute` SHALL NOT declare extra parameters such as `stream=`.

#### Scenario: ports test fake parse_prune returns PruneResult
- **WHEN** the `_Parser` fake in `tests/unit/ports/test_managers.py` calls `parse_prune("")`
- **THEN** it returns a `PruneResult` instance

#### Scenario: ports test fake transport.execute has no stream param
- **WHEN** the `_make_transport` fake in `tests/unit/ports/test_managers.py` is inspected
- **THEN** its `execute` method signature does not include a `stream` parameter

### Requirement: RecordingTransport response keys are tuples
`RecordingTransport` and `RecordingStreamingTransport` SHALL match responses by `tuple(command)`. Tests injecting responses SHALL use `tuple[str, ...]` keys, not space-joined strings, so the lookup actually matches.

#### Scenario: concurrency test response key is a tuple
- **WHEN** `tests/unit/boundary/test_concurrency.py` injects a response for `docker container inspect --format json ctr1`
- **THEN** the key is `("docker", "container", "inspect", "--format", "json", "ctr1")` (a tuple), and the response is matched on execution

### Requirement: Tests must not codify bugs as expected behavior
A test SHALL NOT assert a behavior that the corresponding spec marks as a bug. Specifically: empty `list()` SHALL assert `[]` (not `ParsingError`); empty `pull()` SHALL assert `ImageError` (not `result == ""`).

#### Scenario: empty list test asserts []
- **WHEN** `tests/unit/boundary/test_empty_outputs.py::TestEmptyList` runs
- **THEN** it asserts the manager returns `[]` and does not assert `pytest.raises(ParsingError)`

#### Scenario: empty pull test asserts ImageError
- **WHEN** `tests/unit/boundary/test_empty_outputs.py` runs the empty-pull case
- **THEN** it asserts `pytest.raises(ImageError)` and does not assert `result == ""`

### Requirement: Integration directory holds only real-runtime tests
`tests/integration/` SHALL contain only tests that exercise a real container runtime (skipped when no runtime is present). Mock-based tests SHALL live under `tests/unit/`.

#### Scenario: no mock transport under tests/integration/
- **WHEN** the files under `tests/integration/` are inspected (excluding `__init__.py` and `conftest.py`)
- **THEN** none of them import `RecordingTransport` or `MagicMock` as the system under test

#### Scenario: mock-based workflow test lives under tests/unit/
- **WHEN** `tests/unit/wiring/test_workflows.py` is inspected
- **THEN** it exists and uses `RecordingTransport` (relocated from `tests/integration/functional/test_workflows.py`)
