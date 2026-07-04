## Why

`image.py:39-41` silently drops the user-supplied `files` mapping when `BuildContext.build_file_path` is set without `context_path`. The `positional` becomes `build_file_path.parent` and the tar branch (`:48-52`) is skipped — user thinks they're sending in-memory files; runtime uses the parent directory instead. Additionally, `image.py:45,48` use bare `assert` for production invariants (stripped under `python -O` → `AttributeError` leakage).

## What Changes

- Reject `BuildContext(build_file_path + files)` at `__post_init__` in `domain/types.py:91-111` — symmetric with the existing `context_path + files` rejection at `:104-110`.
- Replace bare `assert context.build_file_content is not None` at `image.py:45,48` with typed `ImageRuntimeError` guards.

## Capabilities

### Modified Capabilities

- `oci-domain-immutability`: `BuildContext` SHALL reject `build_file_path + files` combination at construction.
- `oci-exception-typing`: bare `assert` on production invariants in `image.py` SHALL be replaced with typed `ImageRuntimeError` guards.

## Impact

- **Code**: `domain/types.py:91-111` (add validation), `adapters/managers/image.py:39-52` (replace asserts + add comment).
- **Tests**: `test_build_context_rejects_files_with_build_file_path`, `test_build_with_context_path_raises_on_missing_content`.
- **Risk**: breaking for callers silently setting both — they were already broken; the change makes the bug loud.