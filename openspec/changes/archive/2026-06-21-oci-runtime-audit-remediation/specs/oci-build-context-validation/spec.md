## ADDED Requirements

### Requirement: BuildContext forbids context_path with files
`BuildContext.__post_init__` SHALL raise `ValueError` when both `context_path` is not None and `files` is non-empty. The error message MUST name both fields and explain that `docker build` takes context from either stdin (tar) or a filesystem PATH, not both.

#### Scenario: context_path and files together raises
- **WHEN** `BuildContext(build_file_content="FROM alpine", context_path=Path("/ctx"), files={"a.py": b"x"})` is constructed
- **THEN** construction raises `ValueError` whose message contains `"context_path"` and `"files"`

#### Scenario: context_path without files allowed
- **WHEN** `BuildContext(build_file_content="FROM alpine", context_path=Path("/ctx"))` is constructed
- **THEN** construction succeeds and `ctx.files == {}`

#### Scenario: files without context_path allowed
- **WHEN** `BuildContext(build_file_content="FROM alpine", files={"a.py": b"x"})` is constructed
- **THEN** construction succeeds and `ctx.context_path is None`

### Requirement: BuildContext keeps existing file-content/path mutual exclusion
`BuildContext.__post_init__` SHALL continue to raise `ValueError` when both `build_file_content` and `build_file_path` are set, and when neither is set. The new `context_path`+`files` rule is additional, not a replacement.

#### Scenario: both build file sources raises
- **WHEN** `BuildContext(build_file_content="FROM alpine", build_file_path=Path("/Dockerfile"))` is constructed
- **THEN** construction raises `ValueError`

#### Scenario: neither build file source raises
- **WHEN** `BuildContext()` is constructed
- **THEN** construction raises `ValueError`
