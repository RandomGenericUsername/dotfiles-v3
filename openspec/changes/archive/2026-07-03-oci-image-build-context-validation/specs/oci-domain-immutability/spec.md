## ADDED Requirements

### Requirement: BuildContext deep immutability and mutual exclusivity

`BuildContext` SHALL reject mutual-exclusivity violations at construction:
- `build_file_content` AND `build_file_path` cannot both be set (existing).
- Neither `build_file_content` nor `build_file_path` can be set (existing).
- `context_path` AND `files` cannot both be set (existing).
- `build_file_path` AND `files` cannot both be set (NEW — `files` is for stdin-tar mode only; when `build_file_path` is set the context is filesystem-scoped).

#### Scenario: build_file_path + files rejected
- **WHEN** `BuildContext(build_file_path=Path("Dockerfile"), files={"app.py": b"..."})` is constructed
- **THEN** `ValueError` is raised mentioning that `files` cannot be combined with `build_file_path`

#### Scenario: build_file_path alone accepted
- **WHEN** `BuildContext(build_file_path=Path("Dockerfile"))` is constructed
- **THEN** no error; `files` is empty