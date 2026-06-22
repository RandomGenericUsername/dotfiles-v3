## ADDED Requirements

### Requirement: build() wraps ParsingError in ImageRuntimeError

`CliImageManager.build()` must catch `ParsingError` from `parse_build_output` and re-raise as `ImageRuntimeError` with the original `ParsingError` preserved as `__cause__`. This ensures `except ImageError` catches build output parsing failures, consistent with the operation-level error type. The dead `if not ident or ident == "sha256:":` guard must be removed (unreachable because `parse_build_output` always raises before returning invalid output).

#### Scenario: Build with unparseable output raises ImageRuntimeError
- **WHEN** `build()` calls `parse_build_output()` which raises `ParsingError`
- **THEN** `build()` raises `ImageRuntimeError` with `__cause__` set to the `ParsingError`, and `except ImageError` catches it

#### Scenario: Build with valid output returns image ID
- **WHEN** `parse_build_output()` returns a valid `sha256:<hex>` string
- **THEN** `build()` returns the image ID string without wrapping (no try/except needed)

### Requirement: Podman auth failures use Podman-specific patterns

`PodmanImageParser` must define `_auth_error_patterns` with Podman-specific strings (`"authentication required"`, `"requested access to the resource is denied"`), not Docker's `"pull access denied"`. This ensures `CliImageManager._check_result` raises `ImagePullAccessDeniedError` for Podman auth failures, not `ImageRuntimeError`.

#### Scenario: Podman auth error classified correctly
- **WHEN** `PodmanImageParser.is_auth_error("authentication required")` is called
- **THEN** it returns `True`

#### Scenario: Podman pull access denied raises ImagePullAccessDeniedError
- **WHEN** `CliImageManager.pull()` for Podman gets stderr containing `"authentication required"`
- **THEN** `ImagePullAccessDeniedError` is raised (not `ImageRuntimeError`)
