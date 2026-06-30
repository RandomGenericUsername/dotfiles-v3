## ADDED Requirements

### Requirement: ResultChecker port defines a pure ABC for CLI result checking

`ports/result_checker.py` defines the `ResultChecker` ABC with a single abstract method. The port depends only on `domain.types.RawExecResult` and `domain.exceptions.OciError` — pure domain types, no adapter logic.

```python
class ResultChecker(ABC):
    @abstractmethod
    def check(
        self,
        result: RawExecResult,
        cmd: list[str],
        *,
        operation: str = "execute",
        entity: str = "",
        not_found_error: type[OciError] | None = None,
    ) -> None: ...
```

The `not_found_error` parameter allows per-call overrides (e.g., `ContainerManager.run()` passes `ImageNotFoundError` because the entity being checked is an image, not a container).

#### Scenario: Check passes on zero exit code
- **WHEN** `check(RawExecResult(0, b"ok", b""), ["docker", "ps"])` is called
- **THEN** returns `None` (no exception raised)

#### Scenario: Check raises generic error on non-zero exit without specific match
- **WHEN** `check(RawExecResult(1, b"", b"error: connection refused"), ["docker", "pull", "img"])` is called with `generic_error=ImageRuntimeError`
- **THEN** `ImageRuntimeError` is raised with `command=["docker", "pull", "img"]`, `exit_code=1`, `stderr="error: connection refused"`

#### Scenario: Check raises not-found error when stderr matches pattern
- **WHEN** `check(RawExecResult(1, b"", b"no such container: abc"), ["docker", "inspect", "abc"])` is called with `not_found_error=ContainerNotFoundError` and `is_not_found` matching `"no such container"`
- **THEN** `ContainerNotFoundError("abc")` is raised

#### Scenario: not_found_error override works
- **WHEN** `check(..., entity="myimage:latest", not_found_error=ImageNotFoundError)` is called on a container manager's result checker
- **THEN** `ImageNotFoundError("myimage:latest")` is raised, not `ContainerNotFoundError`

#### Scenario: Auth error raised before not-found (auth takes precedence)
- **WHEN** stderr contains both "pull access denied" and "no such image"
- **THEN** `ImagePullAccessDeniedError` is raised (auth branch checked first)

#### Scenario: Non-image manager skips auth check
- **WHEN** `ResultChecker` is constructed with `auth_error=None` and `is_auth=None`
- **THEN** the auth branch is never entered; not-found and generic branches work normally

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

All error types and detection callables are injected via the constructor. The adapter never imports parser types — it depends on `Callable[[str], bool]`. The `is_not_found` callable is sourced from the parser at wiring time by the factory.

#### Scenario: CliResultChecker uses safe_decode for stderr
- **WHEN** `check` receives a result with raw bytes stderr containing non-UTF8 data
- **THEN** the stderr is decoded with `errors="replace"` via `domain/encoding.safe_decode()`, never raising `UnicodeDecodeError`

#### Scenario: CliResultChecker raises auth error with full context (A4 fix)
- **WHEN** `ImagePullAccessDeniedError` is raised via `check()`
- **THEN** the exception carries `command`, `exit_code`, and `stderr` attributes (requires `ImagePullAccessDeniedError.__init__` update to accept and forward `*args, **kwargs` to `OciError`)

#### Scenario: CliResultChecker cannot be constructed without required error types
- **WHEN** `CliResultChecker(generic_error=None, not_found_error=ContainerNotFoundError, is_not_found=fn)` is attempted
- **THEN** `TypeError` is raised (or construction fails at the type-check level); both `generic_error` and `not_found_error` are required

### Requirement: Factory creates one CliResultChecker per manager

`RuntimeFactory.create()` creates 4 `CliResultChecker` instances, one per manager, with the appropriate error types and parser callables:

```
ContainerManager → CliResultChecker(ContainerRuntimeError, ContainerNotFoundError, container_parser.is_not_found_error)
ImageManager     → CliResultChecker(ImageRuntimeError, ImageNotFoundError, image_parser.is_not_found_error, auth=ImagePullAccessDeniedError, is_auth=image_parser.is_auth_error)
VolumeManager    → CliResultChecker(VolumeRuntimeError, VolumeNotFoundError, volume_parser.is_not_found_error)
NetworkManager   → CliResultChecker(NetworkRuntimeError, NetworkNotFoundError, network_parser.is_not_found_error)
```

The same `ResultChecker` instance is shared between a manager and its `ListExecutor`, ensuring consistent error types for both list and non-list operations.

#### Scenario: Container ResultChecker has no auth capability
- **WHEN** `CliResultChecker` for container operations is constructed
- **THEN** `auth_error` is `None` and `is_auth` is `None`; the auth branch is always skipped

#### Scenario: Image ResultChecker has auth capability
- **WHEN** `CliResultChecker` for image operations is constructed
- **THEN** `auth_error` is `ImagePullAccessDeniedError` and `is_auth` is `image_parser.is_auth_error`
