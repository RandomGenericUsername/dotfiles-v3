## MODIFIED Requirements

### Requirement: Tightened smoke test skip

Smoke tests (`test_basic_commands_present`, etc.) SHALL skip only when the configured runtime binary (`oci_bin` fixture from `OCI_PATH` env or `"docker"` default) is unavailable. The skip guard SHALL use `subprocess.run([oci_bin, "--help"], ...)` rather than `subprocess.run(["oci", "--help"], ...)`.

#### Scenario: Skip only when configured binary missing
- **WHEN** `OCI_PATH=docker` or `OCI_PATH` is unset
- **THEN** the skip guard checks `docker --help` (not `oci --help`)

#### Scenario: Podman binary passes skip
- **WHEN** `OCI_PATH=podman` and `podman --help` succeeds
- **THEN** the test runs (uses `podman` for subsequent commands)