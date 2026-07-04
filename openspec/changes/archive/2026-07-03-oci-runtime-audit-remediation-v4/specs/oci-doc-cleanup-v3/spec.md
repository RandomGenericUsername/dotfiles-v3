## ADDED Requirements

### Requirement: adapters/_utils.py shim is deleted

`adapters/_utils.py` SHALL NOT contain a local `parse_size_to_bytes` definition shadowed by `from oci_runtime.domain.size_parsing import *`. The stale duplicate (with its divergent, stricter regex requiring a unit) is removed entirely. Any test importing `parse_size_to_bytes` from `adapters._utils` SHALL be updated to import from `oci_runtime.domain.size_parsing` directly. This completes the v3 cleanup that already deleted the analogous `adapters/_tar.py` shim.

#### Scenario: adapters/_utils.py contains no parse_size_to_bytes definition
- **WHEN** `adapters/_utils.py` is inspected
- **THEN** it does not define a local `parse_size_to_bytes` function and does not contain `from oci_runtime.domain.size_parsing import *`

#### Scenario: tests import parse_size_to_bytes from the domain
- **WHEN** `tests/audit/test_known_bugs.py` is inspected for its `parse_size_to_bytes` import
- **THEN** the import is `from oci_runtime.domain.size_parsing import parse_size_to_bytes` (not from `adapters._utils`)

### Requirement: ARCHITECTURE.md adapter tree and stdlib list are accurate

`docs/ARCHITECTURE.md` Module Structure tree SHALL list every adapter submodule that exists: `adapters/binary.py`, `adapters/output_stream.py`, `adapters/tty.py`, `adapters/_utils.py`, `adapters/transport/{cli,streaming,pty}.py`, `adapters/managers/{container,image,volume,network}.py`, `adapters/parser/{docker,podman}.py`, `adapters/provider/{docker,podman}.py`, `adapters/engine/cli.py`, `adapters/discovery/cli.py`, `adapters/helpers/{list_executor,result_checker}.py`. The Domain Layer "allowed stdlib" sentence SHALL include `json`, `types`, and `collections.abc` (which the domain actually imports), not just `re`, `abc`, `dataclasses`, `pathlib`, `enum`.

#### Scenario: Adapter tree lists all transport submodules
- **WHEN** the `docs/ARCHITECTURE.md` Module Structure tree is inspected
- **THEN** it lists `adapters/transport/cli.py`, `adapters/transport/streaming.py`, `adapters/transport/pty.py`, `adapters/binary.py`, `adapters/engine/cli.py`, `adapters/discovery/cli.py`, `adapters/output_stream.py`, and `adapters/tty.py`

#### Scenario: Allowed-stdlib list includes json, types, collections.abc
- **WHEN** the Domain Layer section of `ARCHITECTURE.md` is inspected
- **THEN** the allowed-stdlib sentence includes `json`, `types`, and `collections.abc` alongside `re`, `abc`, `dataclasses`, `pathlib`, `enum`
