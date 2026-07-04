## ADDED Requirements

### Requirement: Subcommand enum in domain/enums.py

`domain/enums.py` SHALL define `class Subcommand(str, Enum)` with members for every OCI subcommand used by the manager adapters: `RUN`, `BUILD`, `TAG`, `PUSH`, `PULL`, `RMI`, `RM`, `EXEC`, `LOGS`, `INSPECT`, `STOP`, `START`, `RESTART`, `PRUNE`, `CREATE`, `CONNECT`, `DISCONNECT`, `LIST`, `IMAGE`, `CONTAINER`, `VOLUME`, `NETWORK`. Inheriting from `str` ensures `Subcommand.RUN == "run"` is `True`. The enum SHALL NOT be re-exported from `oci_runtime/__init__.py` (adapter-internal only).

#### Scenario: Enum values match CLI subcommands
- **WHEN** `Subcommand.INSPECT.value` is inspected
- **THEN** it equals `"inspect"`

#### Scenario: Enum not in public __all__
- **WHEN** `oci_runtime.__all__` is inspected
- **THEN** `"Subcommand"` is NOT present

#### Scenario: Manager uses enum value
- **WHEN** `CliContainerManager.inspect("ctr")` builds its command
- **THEN** the command contains `Subcommand.INSPECT.value` (not a bare `"inspect"` string)