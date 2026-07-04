## MODIFIED Requirements

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

## ADDED Requirements

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