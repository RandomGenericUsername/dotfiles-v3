## MODIFIED Requirements

### Requirement: pull() raises ImageRuntimeError on digest-extraction failure

`CliImageManager.pull()` must raise `ImageRuntimeError` (the manager's `_generic_error`) when `parse_digest_from_pull()` returns an empty string. Previously it raised base `ImageError`. The exception carries `command`, `exit_code`, and `stderr` from the transport result.

#### Scenario: Docker pull digest missing raises ImageRuntimeError
- **WHEN** `docker pull alpine` succeeds (exit 0) but stdout has no `Digest: sha256:...` line (e.g., already present, output is just `"Status: Image is up to date for alpine:latest\n"`)
- **THEN** `image_manager.pull("alpine")` raises `ImageRuntimeError` with `command=["docker", "pull", "alpine"]`, `exit_code=0`, `stderr` empty (or the raw stdout if parsed)

#### Scenario: Podman pull digest missing raises ImageRuntimeError
- **WHEN** `podman pull alpine` succeeds but stdout has no parseable digest (already cached)
- **THEN** `ImageRuntimeError` raised with command/exit_code/stderr attached

#### Scenario: Auth error still raises ImagePullAccessDeniedError
- **WHEN** `docker pull private/image` returns exit 1, stderr `"pull access denied"`
- **THEN** `ImagePullAccessDeniedError` raised (not `ImageRuntimeError`); auth path takes precedence