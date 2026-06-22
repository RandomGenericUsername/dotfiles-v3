## ADDED Requirements

### Requirement: build() raises ImageError for unparseable output

`CliImageManager.build()` SHALL raise `ImageRuntimeError` (a subclass of `ImageError`) when `parse_build_output` cannot extract a valid image ID. The `ParsingError` from the parser SHALL be caught and wrapped as `ImageRuntimeError` with the original `ParsingError` preserved as `__cause__`. The dead `if not ident or ident == "sha256:":` guard SHALL be removed (it is unreachable because `parse_build_output` always raises before returning invalid output).

#### Scenario: Build with empty output raises ImageError
- **WHEN** `docker build` returns exit code 0 with empty stdout
- **THEN** `build()` raises `ImageRuntimeError` (subclass of `ImageError`), and `except ImageError` catches it

#### Scenario: Build with invalid hex output raises ImageError
- **WHEN** `docker build` returns exit code 0 with stdout `"sha256:zzzzz"` (invalid hex)
- **THEN** `build()` raises `ImageRuntimeError`, and `except ImageError` catches it

#### Scenario: ParsingError preserved as __cause__
- **WHEN** `build()` raises `ImageRuntimeError` due to unparseable output
- **THEN** `exception.__cause__` is a `ParsingError` instance (the original parser exception)

#### Scenario: except OciError catches build failure
- **WHEN** `build()` raises `ImageRuntimeError`
- **THEN** `except OciError` catches it (ImageRuntimeError → ImageError → OciError hierarchy)

#### Scenario: Build with valid output returns image ID
- **WHEN** `docker build` returns exit code 0 with stdout `"sha256:abc123def456..."` (valid hex)
- **THEN** `build()` returns the image ID string (unchanged behavior)
