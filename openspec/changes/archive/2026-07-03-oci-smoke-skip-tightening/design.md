## Context

Smoke tests skip broadly. Narrow to configured binary only, using `OCI_PATH` fixture.

## Goals / Non-Goals

**Goals:** Skip only when `oci_bin --help` fails for the configured runner.
**Non-Goals:** Rewriting the skip mechanism.

## Decisions

Change `pytest.skip` condition from `subprocess.run(["oci", "--help"], ...)` to `subprocess.run([oci_bin, "--help"], ...)` using the fixture value.

## Risks / Trade-offs

- None.