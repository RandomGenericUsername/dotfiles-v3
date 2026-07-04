## 1. Add context params to *NotFoundError family

- [ ] 1.1 In `src/oci_runtime/domain/exceptions.py:50-88`, add keyword-only `command`/`exit_code`/`stderr` params to `ImageNotFoundError`, `ContainerNotFoundError`, `VolumeNotFoundError`, `NetworkNotFoundError`. Mirror `ImagePullAccessDeniedError:56-70`. Each forwards to `super().__init__(f"...", command=command, exit_code=exit_code, stderr=stderr)`.
- [ ] 1.2 In `src/oci_runtime/domain/result_checking.py:30-31`, change `raise not_found_error(entity)` to `raise not_found_error(entity, command=cmd, exit_code=result.returncode, stderr=stderr_str)`.

## 2. Fix ProviderNotRegisteredError typing

- [ ] 2.1 In `src/oci_runtime/domain/exceptions.py:128-135`, move `from oci_runtime.domain.enums import RuntimeKind` to top-level. Change `def __init__(self, kind):` to `def __init__(self, kind: RuntimeKind):`. Remove the constructor-time import.

## 3. Tests

- [ ] 3.1 Add `TestNotFoundErrorContext` to `tests/unit/domain/test_exceptions.py` covering all four families: assert `.command`, `.exit_code`, `.stderr` populated after `check_cli_result` raises.
- [ ] 3.2 Add `test_provider_not_registered_kind_typed` to same file: assert `.kind is RuntimeKind.DOCKER`.
- [ ] 3.3 Add `test_existing_positional_callers_unbroken`: `ImageNotFoundError("alpine")` works; `.image_name == "alpine"`.
- [ ] 3.4 Run `uv run pytest -q tests/unit/domain/test_exceptions.py` — green.
- [ ] 3.5 Run `uv run --with mypy mypy src/oci_runtime/domain/exceptions.py` — zero errors on the `kind` annotation.
- [ ] 3.6 Run `uv run ruff check .` — green.