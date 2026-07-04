## Context

`build_tar` uses `PosixPath` (banned stdlib) for pure string manipulation. `posixpath` is already in the domain allowlist.

## Goals / Non-Goals

**Goals:** Replace `PosixPath` with `posixpath.normpath`. Verify same output.
**Non-Goals:** Moving `build_tar` out of domain.

## Decisions

`import posixpath; posixpath.normpath(path_str.replace("\\", "/"))` is byte-identical to `str(PosixPath(path_str.replace("\\", "/")))` for all inputs that don't include `..` normalization (which `build_tar` inputs don't).

## Risks / Trade-offs

- `posixpath.normpath` resolves `..` segments differently than `PosixPath` in edge cases. `build_tar` inputs don't contain `..`, so safe.