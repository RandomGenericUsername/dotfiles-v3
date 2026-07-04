## MODIFIED Requirements

### Requirement: CliResultChecker adapter implements ResultChecker with constructor injection

`adapters/helpers/result_checker.py` provides `CliResultChecker`:

```python
class CliResultChecker(ResultChecker):
    def __init__(
        self,
        generic_error: type[OciError],
        not_found_error: type[OciError],
        is_not_found: Callable[[str], bool],
        *,
        auth_error: type[OciError] | None = None,
        is_auth: Callable[[str], bool] | None = None,
    ): ...
```

All error types and detection callables are injected via the constructor. The adapter never imports parser types — it depends on `Callable[[str], bool]`. The `is_not_found` callable is sourced from the parser at wiring time by the factory. The `check()` method delegates to `domain/result_checking.check_cli_result`, which on the auth branch forwards `command`, `exit_code`, and `stderr` to `auth_error` (the `ImagePullAccessDeniedError.__init__` update required by A4 is already present; the caller now actually passes the context).

#### Scenario: CliResultChecker uses safe_decode for stderr
- **WHEN** `check` receives a result with raw bytes stderr containing non-UTF8 data
- **THEN** the stderr is decoded with `errors="replace"` via `domain/encoding.safe_decode()`, never raising `UnicodeDecodeError`

#### Scenario: CliResultChecker raises auth error with full context
- **WHEN** `check(RawExecResult(1, b"", b"pull access denied for foo"), ["docker","pull","foo"], entity="foo")` is called with `auth_error=ImagePullAccessDeniedError` and `is_auth` matching `"pull access denied"`
- **THEN** `ImagePullAccessDeniedError` is raised AND the exception's `command`, `exit_code`, and `stderr` attributes are populated (`command == ["docker","pull","foo"]`, `exit_code == 1`, `stderr` contains `"pull access denied"`)

#### Scenario: CliResultChecker cannot be constructed without required error types
- **WHEN** `CliResultChecker(generic_error=None, not_found_error=ContainerNotFoundError, is_not_found=fn)` is attempted
- **THEN** `TypeError` is raised (or construction fails at the type-check level); both `generic_error` and `not_found_error` are required
