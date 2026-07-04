## MODIFIED Requirements

### Requirement: detach streaming semantics

`container_manager.detach(image, command, ...)` SHALL NOT raise `RuntimeError("already running")`. Instead, it SHALL run the CLI command with `subprocess.run`, stream startup output to stdout, parse the container ID from the output, and return `ContainerId`. The container ID SHALL be parsed from the first line matching a 64-character hex string or the last line before the shell prompt returns.

#### Scenario: Detach returns ContainerId
- **WHEN** `container_manager.detach("nginx:latest", command=None)` succeeds
- **THEN** a `ContainerId` is returned (not a `RuntimeError`)

#### Scenario: Detach output is streamed
- **WHEN** detach runs successfully
- **THEN** stdout contains the container startup log output