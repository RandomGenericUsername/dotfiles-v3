# Build Flag Completeness

## Purpose

Ensures all list() methods delegate to the ListExecutor port, eliminating duplicated inline implementations.

## Requirements

### Requirement: All list() methods delegate to ListExecutor port

`CliContainerManager.list()`, `CliImageManager.list()`, `CliVolumeManager.list()`, `CliNetworkManager.list()` are rewritten as one-line delegates to `self._list_executor.execute_list(subcommand, entity_type, show_all, filters)`. The four copy-pasted inline implementations are deleted. `ListExecutor.execute_list` is the single implementation of list command construction, execution, error-checking, and parsing.

#### Scenario: Container manager list delegates to ListExecutor
- **WHEN** `CliContainerManager.list(show_all=True, filters={"name": "web"})` is called
- **THEN** `self._list_executor.execute_list(["container", "list"], "containers", show_all=True, filters={"name": "web"})` is called and its result returned

#### Scenario: Image manager list delegates to ListExecutor
- **WHEN** `CliImageManager.list(filters={"dangling": "true"})` is called
- **THEN** `self._list_executor.execute_list(["image", "list"], "images", filters={"dangling": "true"})` is called

#### Scenario: Volume manager list delegates to ListExecutor
- **WHEN** `CliVolumeManager.list()` is called
- **THEN** `self._list_executor.execute_list(["volume", "list"], "volumes")` is called

#### Scenario: Network manager list delegates to ListExecutor
- **WHEN** `CliNetworkManager.list()` is called
- **THEN** `self._list_executor.execute_list(["network", "list"], "networks")` is called

### Requirement: _NOT_PROBED sentinel deleted

The module-level `_NOT_PROBED = object()` in `adapters/binary.py` is removed. It was a remnant of the pre-v2 duplicated `_ensure_binary` / `_which_cache` mechanism and is unused.

#### Scenario: Binary.py has no _NOT_PROBED
- **WHEN** `grep -n "_NOT_PROBED" src/oci_runtime/adapters/binary.py` is run
- **THEN** no matches

### Requirement: Dead getattr defensive check removed from ResultChecker

`ResultChecker.check()` receives `is_auth` as a `Callable[[str], bool] | None` parameter. The `getattr(self._parser, "is_auth_error", None)` guard is not needed because `is_auth` is `None` when no auth check is required. This is handled at wiring time by the factory.

#### Scenario: Container ResultChecker checks no auth
- **WHEN** `ResultChecker` for containers calls `check()` with `is_auth=None`
- **THEN** the auth branch is never entered; not-found and generic branches work normally

### Requirement: Dead except clause removed from RuntimeDiscovery

`CliRuntimeDiscovery.available()` catches `(FileNotFoundError, OSError, RuntimeNotAvailableError)` but `transport.probe()` returns `bool` and raises none of these. The `except` block is deleted.

#### Scenario: available() no longer catches dead exceptions
- **WHEN** `available()` is called and `transport.probe()` returns `False`
- **THEN** no exception is caught; the runtime is simply omitted from the available list
