## MODIFIED Requirements

### Requirement: Typed OCI exception hierarchy

All `*NotFoundError` subclasses (`ImageNotFoundError`, `ContainerNotFoundError`, `VolumeNotFoundError`, `NetworkNotFoundError`) SHALL accept keyword-only `command: list[str] | None`, `exit_code: int | None`, `stderr: str | None` parameters and forward them to `OciError.__init__`. `check_cli_result` SHALL forward `command=cmd, exit_code=result.returncode, stderr=stderr_str` to the `not_found_error` call. Existing positional callers (e.g. `ImageNotFoundError("alpine")`) SHALL continue to work without modification.

#### Scenario: Not-found error carries context after checker raises
- **WHEN** `check_cli_result` raises `ImageNotFoundError` due to `is_not_found(stderr)` matching
- **THEN** the raised exception's `.command`, `.exit_code`, and `.stderr` are populated with the CLI command, return code, and stderr from the result

#### Scenario: Existing positional callers unbroken
- **WHEN** `ImageNotFoundError("alpine")` is constructed
- **THEN** `.image_name == "alpine"` and `.command is None` (keyword-only params default to None)