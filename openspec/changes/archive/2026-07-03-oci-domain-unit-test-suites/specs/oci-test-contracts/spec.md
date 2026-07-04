## MODIFIED Requirements

### Requirement: Domain unit test suites

Each domain module in `src/oci_runtime/domain/` SHALL have a corresponding test file in `tests/unit/domain/`. At minimum: `test_types.py` (BuildContext, ContainerId, port types), `test_exceptions.py` (OciError hierarchy, not-found context), `test_enums.py` (RuntimeKind, ContainerState, Subcommand), `test_result_checking.py` (check_cli_result branches), and `test_binary_resolver.py` (edge cases).

#### Scenario: BuildContext construction validation
- **WHEN** `BuildContext(build_file_path=Path("D"), files={"a": b"b"})` is constructed
- **THEN** `ValueError` is raised mentioning `files` cannot be combined with `build_file_path`

#### Scenario: check_cli_result error code branch
- **WHEN** `check_cli_result(result, ...)` receives a non-zero return code
- **THEN** the appropriate `OciError` subclass is raised based on stderr content matching