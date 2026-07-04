## Purpose

Mechanical enforcement of hexagonal architecture layering rules for the oci-runtime module. Ensures domain, ports, adapters, and factory layers respect import direction constraints, stdlib allowlist/banned-list, ports-ABC-only rules, and path FS-method call bans.
## Requirements
### Requirement: Architecture linter enforces zero adapter-to-adapter imports

The `tests/architecture/test_layering.py` linter must forbid any import from `oci_runtime.adapters` in adapter source files *unless* the importing module and the imported module are both in the `adapters` layer. The allowed import targets for the `adapters` layer are strictly `{"domain", "ports", "adapters"}`. The `_ALLOWED_TARGETS` dict at `test_layering.py:35-41` MUST include `"adapters"` in its `adapters` entry, matching the docstring at `test_layering.py:8-10`.

#### Scenario: Adapter importing another adapter passes the linter
- **WHEN** a file in `src/oci_runtime/adapters/` imports `from oci_runtime.adapters.transport._runner import _SubprocessRunner`
- **THEN** `test_no_layering_violations` for that file passes (adapters may depend on adapters)

#### Scenario: Adapter importing domain or ports passes
- **WHEN** an adapter file imports `from oci_runtime.domain.types import PortMapping` or `from oci_runtime.ports.transport import Transport`
- **THEN** the linter passes (no violation)

#### Scenario: Adapter importing factory still fails
- **WHEN** an adapter file imports `from oci_runtime.factory import RuntimeFactory`
- **THEN** the linter fails with a clear violation message (adapters MAY NOT import the composition root)

### Requirement: Shared adapter base classes SHALL be deleted, not relocated to ports

`BaseCliParser`, `CliBaseManager`, and `BaseCliRuntimeProvider` SHALL be **deleted**, not moved to ports. Their shared logic SHALL be handled by:

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

### Requirement: Pure-stdlib helpers SHALL live in domain/

The following pure-stdlib utilities SHALL be placed in `domain/`:

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

### Requirement: Helper ports SHALL live in ports/ with pure ABCs

The following helper ports SHALL be placed in `ports/`:

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

### Requirement: CompositeCancellationToken + compose_tokens SHALL live in ports/cancellation.py

Both SHALL be pure logic (no I/O, no threads) and SHALL move from `adapters/_cancellation.py` to `ports/cancellation.py`:

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

### Requirement: Domain stdlib imports MUST be allowlisted

The `tests/architecture/test_layering.py` linter MUST inspect stdlib imports (not just `oci_runtime.*` imports) for every file in `src/oci_runtime/domain/` and assert that each imported stdlib module is present in an explicit allowlist:

```
_DOMAIN_ALLOWED_STDLIB = {
  "posixpath", "io", "tarfile", "pathlib", "json", "re",
  "dataclasses", "collections", "collections.abc", "types", "enum"
}
```

Adding a new stdlib module to the domain layer's imports requires editing this allowlist AND amending this spec. `os.path` is specifically excluded — pure-Python `posixpath` shall be used instead because tar entry paths are always POSIX-encoded and `os.path` dispatches to `posixpath`/`ntpath` based on `os.name` (environment coupling).

#### Scenario: Domain allows posixpath but rejects os
- **WHEN** `domain/build_tar.py` imports `posixpath`
- **THEN** the linter passes (`posixpath` is in the allowlist)
- **WHEN** `domain/build_tar.py` imports `os`
- **THEN** the linter fails with `domain layer imports banned stdlib: os in domain/build_tar.py`

#### Scenario: Domain allows tarfile and io for in-memory encoding
- **WHEN** `domain/build_tar.py` imports `io` and `tarfile` to operate on `BytesIO` buffers
- **THEN** the linter passes (both are in the allowlist; `tarfile.open(fileobj=BytesIO(...))` is pure-compute on an in-memory buffer)

#### Scenario: Adding a new stdlib module to domain requires a spec edit
- **WHEN** a developer adds `import base64` to `domain/encoding.py` without amending this spec
- **THEN** the linter fails; the developer must either (a) add `"base64"` to `_DOMAIN_ALLOWED_STDLIB` in the test AND amend this spec, or (b) remove the import

### Requirement: Domain MUST NOT import banned stdlib

Independent of the allowlist, the linter MUST explicitly forbid the domain layer from importing the following stdlib modules: `subprocess`, `os`, `shutil`, `select`, `selectors`, `socket`, `sys.stdin`, `sys.stdout`. These represent environment/I/O coupling and have no pure-domain use. The banned list is opt-out cross-cutting (all banned modules are also necessarily absent from the allowlist, but the banned list exists to make the rule executable as `assert module not in imports` separately from the allowlist membership check).

#### Scenario: Domain importing subprocess fails
- **WHEN** any file in `src/oci_runtime/domain/` contains `import subprocess` or `from subprocess import run`
- **THEN** `test_domain_imports_no_banned_stdlib` fails with `domain layer imports banned stdlib: subprocess in <file>`

#### Scenario: Domain importing os fails even if allowlisted
- **WHEN** any file in `src/oci_runtime/domain/` contains `import os`
- **THEN** the linter fails (the banned-stdlib check fires regardless of allowlist state; the allowlist itself never includes `os`)

### Requirement: Ports MUST be ABCs or typed dataclass aggregates

Every `class` declaration in any file under `src/oci_runtime/ports/` MUST satisfy one of:

1. **ABC** — inherits (directly or transitively) from `abc.ABC` AND declares at least one method decorated with `@abstractmethod`.
2. **Typed dataclass aggregate** — is a `@dataclass` whose primary purpose is to bundle typed port collaborator instances or read-only configuration. Examples that satisfy this branch: `Parsers` (bundles parser instances), `RuntimeCapabilities` (read-only capability flags). The class MUST have `@dataclass` decoration and MUST expose only typed fields; no side-effecting methods (`os.read`, `threading.Timer`, `subprocess.Popen`) are permitted on classes in this branch.

This rule has **no carve-out**. Concrete classes with side effects (e.g. `ProcessPipeReader`, `ThreadCancellationToken`, `DeadlineCancellationToken`) MUST NOT live in `ports/`. Their relocation to adapters/ is enforced by the separate `oci-cancellation-adapter-relocation` change; this linter rule is what makes their absence mechanically verifiable.

#### Scenario: Pure ABC passes the linter
- **WHEN** `ports/transport.py` declares `class Transport(ABC)` with `@abstractmethod def execute(...):`
- **THEN** `test_ports_files_are_abstract_only` for that file passes

#### Scenario: Typed dataclass aggregate passes the linter
- **WHEN** `ports/aggregates.py` declares `@dataclass(frozen=True) class Parsers` with only typed fields
- **THEN** `test_ports_files_are_abstract_only` for that file passes

#### Scenario: Concrete class with os.read fails the linter
- **WHEN** `ports/pipe_reader.py` declares `class ProcessPipeReader(PipeReader)` that calls `os.read` in a non-abstract method body
- **THEN** `test_ports_files_are_abstract_only` fails with `ports/pipe_reader.py declares concrete class 'ProcessPipeReader' which is neither an ABC nor a @dataclass aggregate; relocate to adapters/`

#### Scenario: Concrete class with threading.Timer fails the linter
- **WHEN** `ports/cancellation.py` declares `class DeadlineCancellationToken` that constructs a `threading.Timer` in `__init__`
- **THEN** `test_ports_files_are_abstract_only` fails with `ports/cancellation.py declares concrete class 'DeadlineCancellationToken' which is neither an ABC nor a @dataclass aggregate; relocate to adapters/`

### Requirement: pathlib.Path FS-method calls are forbidden in domain

`pathlib.Path` is admitted to the `_DOMAIN_ALLOWED_STDLIB` allowlist because `Path` instances as field-type annotations (`BuildContext.build_file_path: Path | None`, `VolumeMount.source: str | Path | None`) are value objects — typed wrappers around path strings. The architectural concern with `Path` is its filesystem-touching *methods* (`Path.exists()`, `Path.read_text()`, `Path.read_bytes()`, `Path.write_text()`, `Path.glob()`, `Path.rglob()`, `Path.iterdir()`, `Path.mkdir()`, `Path.rmdir()`, `Path.unlink()`), not the type itself. The linter MUST enforce this distinction via AST inspection: every call expression `<expr>.<method>(...)` inside any file under `src/oci_runtime/domain/` where `<method>` is in the banned FS-method set MUST fail the linter, regardless of whether `<expr>` is statically known to be a `Path` (conservative: any call to a banned method name is flagged; false positives are caught at code review).

The banned FS-method set is: `{"exists", "read_text", "read_bytes", "write_text", "write_bytes", "glob", "rglob", "iterdir", "mkdir", "rmdir", "unlink", "chmod", "chown", "stat", "lstat", "touch"}`.

#### Scenario: Domain code constructs Path but does not call .exists()
- **WHEN** `domain/types.py` declares `build_file_path: Path | None` as a field type
- **THEN** the linter passes (Path as a type is allowed; FS-method calls are what's banned)

#### Scenario: Domain code calling Path.exists() fails
- **WHEN** `domain/some_module.py` contains `if build_file_path.exists():` (a call to the banned method name `exists`)
- **THEN** `test_domain_no_path_fs_method_calls` fails with `domain/some_module.py:line N calls Path.exists() — FS methods on Path are forbidden in domain; delegate to an adapter`

#### Scenario: Domain code calling .read_text() on a non-Path object still fails (conservative)
- **WHEN** `domain/some_module.py` contains `text = data.read_text()` where `data` is bytes (not a Path)
- **THEN** the linter fails (conservative flag — call site should rename to `decode()` or move the operation to an adapter; false positive caught at review)

