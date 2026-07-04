## Why

`build_tar` in `adapters/managers/image.py:75` creates a `PosixPath` from a Windows-style path (`path.replace("\\", "/")`) then immediately converts to string. The `PosixPath` import is from `pathlib` — a stdlib module that is on the banned-stdlist. The function is pure path string manipulation (no filesystem I/O). Swapping to `posixpath` (standard library, already in domain allowlist) keeps the function in domain.

v3 proposed re-extracting `build_tar` to adapters/. v5 rejects that: the function is pure encoding, domain-appropriate. The fix is `posixpath` instead of `PosixPath`.

## What Changes

- In `domain/build_tar.py`, replace `from pathlib import PosixPath` with `import posixpath`.
- Replace `PosixPath(path_str.replace("\\", "/"))` with `posixpath.normpath(path_str.replace("\\", "/"))`.
- Move `build_tar` to `domain/` if not already (it was in adapters; confirmed it's already in `domain/`).

## Capabilities

### Modified Capabilities

- `oci-strict-hexagonal-layering`: `build_tar` SHALL use `posixpath` (banned-stdlist clean) and remain in domain.

## Impact

- **Code**: `domain/build_tar.py` (swap import + call sites).
- **Tests**: existing `test_build_tar` green.
- **Risk**: low — `posixpath.normpath` is a near-direct equivalent.