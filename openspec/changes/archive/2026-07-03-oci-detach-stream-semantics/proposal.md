## Why

`detach` mode currently raises `RuntimeError` ("Container … already running and cannot be started again"). The user wants streaming startup output + returning the parsed container id. v3 had complex async; v5 simplifies to: CLI command runs to completion, stdout is streamed, container id is parsed from output.

## What Changes

- Remove the "already running" rejection in `container_manager.detach`.
- Run the CLI command with `subprocess.run`, capture stdout, parse container id from stream output.
- Return `ContainerId` after parsing.

## Capabilities

### Modified Capabilities

- `oci-pty-timeout`: `detach` SHALL stream startup output and return `ContainerId`; SHALL NOT raise "already running".

## Impact

- **Code**: `adapters/managers/container.py` (rewrite `detach`).
- **Tests**: update `test_container_detach` to expect `ContainerId`.
- **Risk**: medium — behavior change; existing callers expecting `RuntimeError` will break.