## Why

v4 A4 wired `auth_error` in `check_cli_result` to forward `command`/`exit_code`/`stderr` (`result_checking.py:23-29`). The not-found path at `:30-31` still drops context — calls `raise not_found_error(entity)` with no context. The four `*NotFoundError` classes (`exceptions.py:50-88`) accept only entity id. Separately, `ProviderNotRegisteredError` (`exceptions.py:128-135`) imports `RuntimeKind` inside the constructor and leaves `kind` untyped.

## What Changes

- Add keyword-only `command`/`exit_code`/`stderr` params to all four `*NotFoundError` classes (mirror `ImagePullAccessDeniedError:56-70`).
- Update `result_checking.py:30-31` to forward context to `not_found_error`.
- Move `RuntimeKind` import to top-level in `exceptions.py`; annotate `kind: RuntimeKind`.

## Capabilities

### Modified Capabilities

- `oci-exception-typing`: `*NotFoundError` classes SHALL accept keyword-only context params; `check_cli_result` SHALL forward context to not-found errors.
- `oci-version-error-contract`: `ProviderNotRegisteredError.kind` SHALL be typed `RuntimeKind`; import SHALL be top-level.

## Impact

- **Code**: `domain/exceptions.py:50-88` (add keyword-only params to 4 classes), `domain/exceptions.py:128-135` (top-level import + annotation), `domain/result_checking.py:30-31` (forward context).
- **Tests**: `TestNotFoundErrorContext` covering all four families; existing `ImageNotFoundError("alpine")` calls still work (keyword-only additions).
- **Risk**: none — keyword-only additions don't break positional callers.