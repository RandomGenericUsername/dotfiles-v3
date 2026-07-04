## RECONCILED Requirements

### Requirement: build_tar stays in domain with posixpath

`domain/build_tar.py:build_tar` SHALL use `import posixpath` and `posixpath.normpath(...)` instead of `from pathlib import PosixPath`. The function SHALL remain in `domain/` (not re-extracted to adapters). It SHALL NOT import from `pathlib` (banned stdlib for domain).

#### Scenario: build_tar produces correct tar
- **WHEN** `build_tar("dir", "file")` is called
- **THEN** the tar output is byte-identical to before the swap (same tar header names)

#### Scenario: No pathlib import in domain/build_tar
- **WHEN** `domain/build_tar.py` is scanned for `pathlib`
- **THEN** no match is found