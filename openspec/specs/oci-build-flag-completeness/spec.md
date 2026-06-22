## ADDED Requirements

### Requirement: Build must emit all BuildContext flags

`ImageManager.build()` must emit CLI flags for every documented `BuildContext` field. No field that the user sets may be silently dropped. Specifically:

- `build_args`: each key-value pair must produce `--build-arg KEY=VALUE`
- `labels`: each key-value pair must produce `--label KEY=VALUE`
- `pull=True`: must produce `--pull`
- `rm=False`: must produce `--rm=false` (default `rm=True` omits the flag)
- `network`: must produce `--network VALUE`
- `build_contexts`: each entry must produce `--build-context KEY=VALUE`

Fields that are `None`, empty, or at their default value may be omitted (no flag emitted). But a field the user explicitly sets must appear in the command.

#### Scenario: Build with build_args
- **WHEN** `BuildContext(build_file_content="FROM alpine", build_args={"HTTP_PROXY": "http://proxy"})` is built
- **THEN** the emitted command contains `--build-arg HTTP_PROXY=http://proxy`

#### Scenario: Build with labels
- **WHEN** `BuildContext(build_file_content="FROM alpine", labels={"maintainer": "team"})` is built
- **THEN** the emitted command contains `--label maintainer=team`

#### Scenario: Build with pull
- **WHEN** `BuildContext(build_file_content="FROM alpine", pull=True)` is built
- **THEN** the emitted command contains `--pull`

#### Scenario: Build with network
- **WHEN** `BuildContext(build_file_content="FROM alpine", network="host")` is built
- **THEN** the emitted command contains `--network host`

#### Scenario: Build with rm=False
- **WHEN** `BuildContext(build_file_content="FROM alpine", rm=False)` is built
- **THEN** the emitted command contains `--rm=false`
