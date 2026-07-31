# directory-resolution Specification

## Purpose
TBD - created by archiving change config-assembler-dir-resolution. Update Purpose after archive.
## Requirements
### Requirement: Strategies declare resource kind

Every strategy SHALL accept a required keyword-only `kind` parameter of type `ResourceKind`.

- `ResourceKind.FILE` — strategy validates with `Path.is_file()`
- `ResourceKind.DIRECTORY` — strategy validates with `Path.is_dir()`

#### Scenario: FILE strategy rejects directory at resolution

- **WHEN** `DefaultFileStrategy(path=directory, kind=ResourceKind.FILE).resolve(policy)` is called on a path that is a directory
- **THEN** the strategy returns `None`

#### Scenario: DIR strategy rejects file at resolution

- **WHEN** `DefaultDirStrategy(path=file).resolve(policy)` is called on a path that is a file
- **THEN** the strategy returns `None`

#### Scenario: Missing kind raises TypeError

- **WHEN** any strategy is constructed without the `kind` argument
- **THEN** a `TypeError` is raised

### Requirement: Directory strategy subclasses

Each file-strategy SHALL have a directory-subclass counterpart that presets `kind=DIRECTORY`:

| File strategy | Directory subclass |
|---|---|
| `CliPathStrategy` | `CliDirStrategy` |
| `EnvPathStrategy` | `EnvDirStrategy` |
| `DirectoryTraversalStrategy` | `DirTraversalStrategy` |
| `XdgStrategy` | `XdgDirStrategy` |
| `DefaultFileStrategy` | `DefaultDirStrategy` |

Subclasses SHALL NOT require the caller to specify `kind`.

#### Scenario: Directory subclass automatically sets DIRECTORY

- **WHEN** `DefaultDirStrategy(path=some_dir)` is constructed
- **THEN** its internal kind equals `ResourceKind.DIRECTORY`
- **THEN** it returns a `ResolvedPath` with `kind=ResourceKind.DIRECTORY` on match

#### Scenario: Directory subclass rejects a file

- **WHEN** `DefaultDirStrategy(path=some_file).resolve(policy)` is called on a file path
- **THEN** it returns `None`

### Requirement: ResolvedPath carries kind

`ResolvedPath` SHALL have a `kind: ResourceKind` field set by the resolving strategy. The default value SHALL be `ResourceKind.FILE` for backward compatibility.

#### Scenario: ResolvedPath from FILE strategy has kind=FILE

- **WHEN** a file is resolved via `DefaultFileStrategy(path=file, kind=ResourceKind.FILE)`
- **THEN** `result.kind == ResourceKind.FILE`

#### Scenario: ResolvedPath from DIR strategy has kind=DIRECTORY

- **WHEN** a directory is resolved via `DefaultDirStrategy(path=dir)`
- **THEN** `result.kind == ResourceKind.DIRECTORY`

### Requirement: AssembleDir resolves a directory and lists contents

The engine SHALL provide an `AssembleDir` use case that:
1. Accepts a list of strategies and an optional file glob pattern
2. Resolves a directory path using `CompositePathResolver`
3. Validates the resolved path is a directory
4. Lists files matching the pattern within that directory
5. Returns a `DirAssemblyResult(directory, source, files)`

#### Scenario: AssembleDir resolves and lists matching files

- **WHEN** `AssembleDir(strategies=[DefaultDirStrategy(path=dir)], file_pattern="*.j2").execute(policy)` is called on a directory containing multiple `.j2` files and a `.md` file
- **THEN** `result.directory` equals the resolved directory path
- **THEN** `result.files` contains only the `.j2` files

#### Scenario: AssembleDir raises when resolved path is not a directory

- **WHEN** `AssembleDir(strategies=[DefaultFileStrategy(path=file, kind=ResourceKind.FILE)]).execute(policy)` resolves to a file path
- **THEN** a `NotADirectoryError` is raised

#### Scenario: AssembleDir raises when no strategy matches

- **WHEN** no strategy in the chain resolves a path
- **THEN** a `PathResolutionError` is raised

