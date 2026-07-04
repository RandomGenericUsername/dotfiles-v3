# oci-named-constants Specification

## Purpose
Named constants replace magic numbers across transport, manager, and pipe-reader modules without introducing a central constants module.
## Requirements
### Requirement: Per-module named constants replace magic numbers

Transport, manager, and pipe-reader modules SHALL define named constants for inlined magic numbers. No central constants module SHALL be created (cross-layer coupling anti-pattern). The following constants SHALL be defined at module scope:

| Module | Constant | Value | Replaces |
|--------|----------|-------|----------|
| `adapters/transport/cli.py` | `_STDIN_JOIN_TIMEOUT` | `5.0` | `timeout=5` at `:129` |
| `adapters/transport/streaming.py` | `_STDIN_JOIN_TIMEOUT` | `5.0` | `timeout=5` at `:84,94` |
| `adapters/managers/container.py` | `_DEFAULT_STOP_TIMEOUT_SECONDS` | `10` | `"10"` at `:213,226` |
| `ports/pipe_reader.py` | `_READ_CHUNK` | `4096` | `4096` at `:56` |

#### Scenario: stdin join timeout is named
- **WHEN** `CliTransport.execute` joins the stdin thread
- **THEN** the timeout value is `_STDIN_JOIN_TIMEOUT` (not a bare `5`)

#### Scenario: pipe read chunk size is named
- **WHEN** `ProcessPipeReader._read_fd` reads from a file descriptor
- **THEN** the chunk size is `_READ_CHUNK` (not a bare `4096`)

