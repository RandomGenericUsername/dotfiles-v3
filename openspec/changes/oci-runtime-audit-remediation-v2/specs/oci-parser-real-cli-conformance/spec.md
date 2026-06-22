## MODIFIED Requirements

### Requirement: Parsers must round-trip real CLI output

All parser methods must produce valid domain objects when fed real docker/podman CLI output, not just imagined JSON. The conformance fixtures in `tests/conformance/fixtures/` are committed ground truth captured from live daemons. The parsers must handle the actual shapes the CLIs emit, including:

- `docker ps --format '{{json .}}'` emits `Names` as a **string** (e.g. `"mycontainer"`), not a list
- `podman ps --format json` emits `Ports` as `null` when no ports are mapped
- Both runtimes emit `Labels: null` in inspect output when the entity has no labels
- `podman pull` for a cached image emits a bare hex id without `sha256:` prefix
- Docker `image inspect` returns `"RepoTags": null` for untagged images; Podman returns `"RepoTags": []` — both must produce an empty list

#### Scenario: Docker container list with string Names
- **WHEN** `DockerContainerParser.parse_list()` is fed real `docker ps --format '{{json .}}'` output where `Names` is a string
- **THEN** it returns `list[ContainerInfo]` without raising, and `info.name` is the string value (not a crash)

#### Scenario: Podman container list with null Ports
- **WHEN** `PodmanContainerParser.parse_list()` is fed real `podman ps --format json` output where `Ports` is `null`
- **THEN** it returns `list[ContainerInfo]` without raising, and `info.ports` is `[]`

#### Scenario: Podman container inspect with null Labels
- **WHEN** `PodmanContainerParser.parse_inspect()` is fed real output where `Labels` is `null`
- **THEN** `info.labels` is `{}` (empty mapping), not `None`

#### Scenario: Docker volume inspect with null Labels
- **WHEN** `DockerVolumeParser.parse_inspect()` is fed real output where `Labels` is `null`
- **THEN** `info.labels` is `{}` (empty mapping), not `None`

#### Scenario: Podman pull returns sha256-prefixed id
- **WHEN** `PodmanImageParser.parse_digest_from_pull()` is fed real podman pull output that contains a bare hex id
- **THEN** the returned string is `sha256:`-prefixed, not a bare hex string

#### Scenario: Podman image inspect with null RepoTags
- **WHEN** `PodmanImageParser.parse_inspect()` is fed real output where `RepoTags` is `null`
- **THEN** `info.tags` is `[]` (empty tuple after deep-freeze), not `None`, and iterating does not raise `TypeError`

#### Scenario: All inspect labels are dict-typed
- **WHEN** any parser's `parse_inspect` is fed real CLI output
- **THEN** the resulting domain object's `labels` field is always a `Mapping` (MappingProxyType), never `None`
