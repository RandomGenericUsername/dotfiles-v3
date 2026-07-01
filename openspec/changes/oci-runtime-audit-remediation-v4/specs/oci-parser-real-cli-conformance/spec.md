## ADDED Requirements

### Requirement: Conformance fixtures cover container list with published ports

`tests/conformance/fixtures/docker/` SHALL include a real `docker container ls --format '{{json .}}'` capture for a container with at least one published port (so the `Ports` field is a non-empty string, exercising the string-parsing path). The docker and podman parser conformance tests SHALL round-trip this fixture and assert the resulting `ContainerInfo.ports` is non-empty and matches the published binding.

#### Scenario: Docker list fixture with published ports exists
- **WHEN** the conformance fixture directory is inspected
- **THEN** a `docker/container_list_with_ports.json` fixture exists and its `Ports` field is a non-empty string

#### Scenario: Docker list conformance test parses ports
- **WHEN** `test_docker_parse_list_produces_valid_container_info` runs against the with-ports fixture
- **THEN** the resulting `ContainerInfo.ports` is non-empty and contains a `PortMapping` with a non-`None` `host_port`

### Requirement: Conformance fixtures cover prune and build output

`tests/conformance/capture.py` SHALL capture `docker/podman image prune --force` output (against a dedicated sentinel image so real images are not lost) and `docker/podman build` progress output (from `echo FROM alpine | <runtime> build -t conformance -`). The conformance tests SHALL round-trip `parse_prune_result` and `parse_build_output` against these real captures, anchoring the two parser methods most likely to break across CLI versions.

#### Scenario: prune conformance test asserts a positive deleted count
- **WHEN** the prune conformance test runs against the captured prune fixture
- **THEN** `parse_prune_result(fixture)` returns `PruneResult(deleted >= 1)` with the capitalized `Deleted:` lines counted (docker)

#### Scenario: build conformance test asserts a sha256 image id
- **WHEN** the build conformance test runs against the captured build fixture
- **THEN** `parse_build_output(fixture)` returns a string matching `^sha256:[a-f0-9]{12,64}$`

### Requirement: Podman network inspect conformance fixture exists

`tests/conformance/fixtures/podman/network_inspect_bridge.json` SHALL exist as a committed fixture (captured once from a real podman daemon), so the podman network-inspect conformance test is NOT `skipif`-gated on a live daemon and runs in CI.

#### Scenario: Podman network inspect fixture is committed
- **WHEN** the conformance fixture directory is inspected
- **THEN** `podman/network_inspect_bridge.json` exists

### Requirement: Docker and Podman parsers produce equivalent domain objects

The conformance tests SHALL include a parity assertion: for the shared alpine image and the bridge network, the docker and podman parsers SHALL produce equivalent `ImageInfo`/`NetworkInfo` (e.g. `docker_info.id.lstrip("sha256:") == podman_info.id`, `set(docker_info.tags) == set(podman_info.tags)`). A parser that silently drops or renames a field for one runtime SHALL fail the parity test.

#### Scenario: Image id parity across runtimes
- **WHEN** both `docker/image_inspect_alpine.json` and `podman/image_inspect_alpine.json` are parsed
- **THEN** `docker_info.id.lstrip("sha256:") == podman_info.id` and `set(docker_info.tags) == set(podman_info.tags)`
