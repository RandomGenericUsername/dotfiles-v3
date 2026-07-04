## ADDED Requirements

### Requirement: CLI timeout values are rendered via ceil

`CliContainerManager.stop` and `CliContainerManager.restart` SHALL render the Docker CLI `-t` flag value using `math.ceil(timeout)` so fractional timeouts are never under-applied. The helper `cli_seconds(timeout: float | None, default: int) -> str` SHALL live in `adapters/managers/_timeouts.py` and be used by both call sites.

#### Scenario: Fractional timeout rounds up
- **WHEN** `container.stop("ctr", timeout=1.9)` is called
- **THEN** the CLI command contains `["-t", "2"]` (not `"1"`)

#### Scenario: Integer timeout passes through
- **WHEN** `container.stop("ctr", timeout=10.0)` is called
- **THEN** the CLI command contains `["-t", "10"]`

#### Scenario: None timeout uses default
- **WHEN** `container.stop("ctr", timeout=None)` is called
- **THEN** the CLI command contains `["-t", "10"]` (the default)

#### Scenario: Sub-second timeout rounds to 1
- **WHEN** `container.stop("ctr", timeout=0.5)` is called
- **THEN** the CLI command contains `["-t", "1"]` (ceil(0.5) == 1, and max(1, ...) floor)