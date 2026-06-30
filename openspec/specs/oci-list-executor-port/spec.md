## ADDED Requirements

### Requirement: ListExecutor port defines a pure generic ABC for the list pattern

`ports/list_executor.py` defines `ListExecutor[T]` with a single abstract method. The port depends only on `typing.Generic` and stdlib — no adapter types, no I/O interfaces.

```python
T = TypeVar("T")

class ListExecutor(ABC, Generic[T]):
    @abstractmethod
    def execute_list(
        self,
        subcommand: list[str],
        entity_type: str,
        *,
        show_all: bool = False,
        filters: dict[str, str] | None = None,
    ) -> list[T]: ...
```

The generic type parameter `T` binds at wiring time: `ListExecutor[ContainerInfo]` for containers, `ListExecutor[ImageInfo]` for images, etc.

#### Scenario: Container list returns list[ContainerInfo]
- **WHEN** `ListExecutor[ContainerInfo].execute_list(["container", "list"], "containers")` succeeds
- **THEN** returns `list[ContainerInfo]` (statically typed; runtime inferred from `parse_list` callable)

#### Scenario: Image list returns list[ImageInfo]
- **WHEN** `ListExecutor[ImageInfo].execute_list(["image", "list"], "images")` succeeds
- **THEN** returns `list[ImageInfo]`

### Requirement: CliListExecutor adapter implements ListExecutor with constructor injection

`adapters/helpers/list_executor.py` provides `CliListExecutor[T]`:

```python
class CliListExecutor(ListExecutor[T]):
    def __init__(
        self,
        transport: Transport,
        caps: RuntimeCapabilities,
        result_checker: ResultChecker,
        parse_list: Callable[[str], list[T]],
    ): ...
```

The adapter receives its collaborators via constructor injection:
- `transport` for command execution
- `caps` for format flags
- `result_checker` for error checking (shared with the parent manager)
- `parse_list` callable sourced from the parser at wiring time

The adapter uses `domain/list_command.build_list_command()` for command construction and `domain/encoding.safe_decode()` for stdout decoding.

#### Scenario: execute_list builds command correctly
- **WHEN** `CliListExecutor.execute_list(["container", "list"], "containers", show_all=True, filters={"name": "web"})` is called
- **THEN** the executed command is `["docker", "container", "list", "--format", "{{json .}}", "-a", "--filter", "name=web"]` (subcommand + format flags + show_all + filters)

#### Scenario: execute_list delegates to result_checker
- **WHEN** the transport returns a non-zero exit
- **THEN** `result_checker.check(result, cmd, operation=f"list {entity_type}")` is called; if it raises, the exception propagates

#### Scenario: execute_list calls parse_list with decoded stdout
- **WHEN** transport returns `RawExecResult(0, b'[{"Id":"abc"}]', b'')`
- **THEN** `parse_list('[{"Id":"abc"}]')` is called (decoded via `safe_decode`)
- **AND** the returned `list[T]` is returned from `execute_list`

#### Scenario: Transport execute errors propagate through result_checker
- **WHEN** transport raises `OperationTimeoutError` (e.g., from a deadline token)
- **THEN** the exception propagates unmodified; `CliListExecutor` does not catch it

#### Scenario: CliListExecutor depends only on ports + domain
- **WHEN** source files are scanned for import violations
- **THEN** `CliListExecutor` imports only from `oci_runtime.domain.*` and `oci_runtime.ports.*`; no imports from `oci_runtime.adapters.*`

### Requirement: Factory creates one CliListExecutor per manager with type-specific parse_list

`RuntimeFactory.create()` creates 4 `CliListExecutor` instances:

```
ContainerManager → CliListExecutor[ContainerInfo](transport, caps, container_checker, container_parser.parse_list)
ImageManager     → CliListExecutor[ImageInfo](transport, caps, image_checker, image_parser.parse_list)
VolumeManager    → CliListExecutor[VolumeInfo](transport, caps, volume_checker, volume_parser.parse_list)
NetworkManager   → CliListExecutor[NetworkInfo](transport, caps, network_checker, network_parser.parse_list)
```

Each executor shares its `result_checker` with the parent manager, ensuring `ContainerRuntimeError` is raised for container operations, `ImageRuntimeError` for image operations, etc.

#### Scenario: Container manager list delegates to ListExecutor
- **WHEN** `CliContainerManager.list(show_all=True, filters={"name": "web"})` is called
- **THEN** `self._list_executor.execute_list(["container", "list"], "containers", show_all=True, filters={"name": "web"})` is called
- **AND** the returned `list[ContainerInfo]` is returned from `list()`

#### Scenario: Image manager list delegates to ListExecutor
- **WHEN** `CliImageManager.list(filters={"dangling": "true"})` is called
- **THEN** `self._list_executor.execute_list(["image", "list"], "images", filters={"dangling": "true"})` is called

#### Scenario: Volume manager list delegates to ListExecutor
- **WHEN** `CliVolumeManager.list()` is called
- **THEN** `self._list_executor.execute_list(["volume", "list"], "volumes")` is called

#### Scenario: Network manager list delegates to ListExecutor
- **WHEN** `CliNetworkManager.list()` is called
- **THEN** `self._list_executor.execute_list(["network", "list"], "networks")` is called
