## Why

`tests/smoke/test_oci_integration.py:7,25` blanket-skips if `oci --help` fails. After `OCI_PATH` env-var approach, we can skip only when the configured runtime binary is missing, not when any runtime is missing.

## What Changes

- Tighten skip condition: check `oci --help` specifically for the configured `OCI_BIN` (default `docker`), not a hardcoded binary.
- Keep the `OCI_PATH` fixture already used; just narrow the skip guard.

## Capabilities

### Modified Capabilities

- `oci-test-contracts`: smoke tests SHALL skip only when the configured runtime binary is unavailable.