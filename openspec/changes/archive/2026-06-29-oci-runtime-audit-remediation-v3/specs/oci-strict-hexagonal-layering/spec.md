## ADDED Requirements

### Requirement: Architecture linter enforces zero adapter-to-adapter imports

The `tests/architecture/test_layering.py` linter must forbid any import from `oci_runtime.adapters` in adapter source files. The allowed import targets for the `adapters` layer are strictly `{"domain", "ports"}`.

#### Scenario: Adapter importing another adapter fails the linter
- **WHEN** a file in `src/oci_runtime/adapters/` imports `from oci_runtime.adapters.binary import CliBinaryResolver`
- **THEN** `test_no_layering_violations` for that file fails with a clear violation message

#### Scenario: Adapter importing domain or ports passes
- **WHEN** an adapter file imports `from oci_runtime.domain.types import PortMapping` or `from oci_runtime.ports.transport import Transport`
- **THEN** the linter passes (no violation)

### Requirement: No shared adapter base classes live in ports/

`BaseCliParser`, `CliBaseManager`, and `BaseCliRuntimeProvider` are **deleted**, not moved to ports. Their shared logic is handled by:

1. **Pure domain helpers** — for stdlib-only logic (JSON parsing, error matching, prune parsing, size parsing, tar building, list command building, encoding, result checking).
2. **Helper ports with pure ABCs** — for coordination patterns that involve other ports (`ResultChecker` for result checking, `ListExecutor[T]` for the list pattern).
3. **Direct ABC implementation** — each concrete adapter implements the existing port ABCs directly.

The following port modules from the v3 plan are NOT created:
- `ports/parser_base.py` — not created; parsers implement port ABCs directly
- `ports/manager_base.py` — not created; managers implement port ABCs directly
- `ports/provider_base.py` — not created; providers implement `RuntimeProvider` directly

#### Scenario: Docker container parser does not inherit from BaseCliParser
- **WHEN** `DockerContainerParser` is defined as `class DockerContainerParser(ContainerParser)`
- **THEN** it does not import `BaseCliParser` from any location; it calls domain helpers directly

#### Scenario: Container manager does not inherit from CliBaseManager
- **WHEN** `CliContainerManager` is defined as `class CliContainerManager(ContainerManager)`
- **THEN** it receives `ResultChecker` and `ListExecutor` via constructor injection

#### Scenario: Docker provider does not inherit from BaseCliRuntimeProvider
- **WHEN** `DockerRuntimeProvider` is defined as `class DockerRuntimeProvider(RuntimeProvider)`
- **THEN** it receives parser classes via constructor injection from the factory

### Requirement: Pure-stdlib helpers live in domain/

The following pure-stdlib utilities are placed in `domain/`:

| Module | Functions |
|--------|-----------|
| `domain/build_tar.py` | `create_build_tar`, `_validate_tar_path` |
| `domain/size_parsing.py` | `parse_size_to_bytes`, `coerce_size`, `safe_int` |
| `domain/json_parsing.py` | `parse_json_item`, `parse_json_list` |
| `domain/error_matching.py` | `matches_any_pattern` |
| `domain/prune_parsing.py` | `parse_prune_result` |
| `domain/list_command.py` | `build_list_command` |
| `domain/encoding.py` | `safe_decode` |
| `domain/result_checking.py` | `check_cli_result` |

#### Scenario: Docker image parser imports parse_json_item from domain
- **WHEN** `DockerImageParser.parse_inspect` needs JSON parsing
- **THEN** it imports `from oci_runtime.domain.json_parsing import parse_json_item`

#### Scenario: Docker container parser imports matches_any_pattern from domain
- **WHEN** `DockerContainerParser.is_not_found_error(stderr)` is called
- **THEN** it delegates to `matches_any_pattern(stderr, self._not_found_patterns)` from `domain/error_matching.py`

### Requirement: Helper ports live in ports/ with pure ABCs

| Port | Module | Purpose |
|------|--------|---------|
| `ResultChecker` | `ports/result_checker.py` | Pure ABC for the check-result pattern |
| `ListExecutor[T]` | `ports/list_executor.py` | Pure ABC for the build-execute-check-parse list pattern, generic over return type |
| `PipeReader` | `ports/pipe_reader.py` | Pure ABC for fd-based subprocess/PTY output reading |

#### Scenario: Transport receives PipeReader via factory, not direct import
- **WHEN** `CliTransport` is constructed
- **THEN** it receives a `pipe_reader_factory` from the factory, and does not import `oci_runtime.adapters._process_reader.ProcessPipeReader`

#### Scenario: Manager receives ResultChecker via factory, not internal construction
- **WHEN** `CliContainerManager` is constructed
- **THEN** it receives a `ResultChecker` instance from the factory, and does not import `oci_runtime.helpers.result_checker.CliResultChecker`

### Requirement: CompositeCancellationToken + compose_tokens live in ports/cancellation.py

Both are pure logic (no I/O, no threads) and move from `adapters/_cancellation.py` to `ports/cancellation.py`:

- `CompositeCancellationToken` — delegates `cancel()` to children; `is_cancelled` checks all children.
- `compose_tokens(*tokens)` — combines optional tokens into a single `CompositeCancellationToken`; returns `None` if all tokens are `None`.

`ThreadCancellationToken` and `DeadlineCancellationToken` remain in `adapters/_cancellation.py` (they manage `threading.Event` and `threading.Timer` — internal state).

#### Scenario: compose_tokens with two tokens returns CompositeCancellationToken
- **WHEN** `compose_tokens(user_token, deadline_token)` is called with both tokens non-None
- **THEN** returns `CompositeCancellationToken(user_token, deadline_token)`

#### Scenario: compose_tokens with one token returns that token directly
- **WHEN** `compose_tokens(None, deadline_token)` is called
- **THEN** returns `deadline_token` (no wrapping)

#### Scenario: compose_tokens with all None returns None
- **WHEN** `compose_tokens(None, None)` is called
- **THEN** returns `None`
