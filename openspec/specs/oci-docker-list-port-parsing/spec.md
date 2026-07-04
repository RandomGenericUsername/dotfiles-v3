# oci-docker-list-port-parsing Specification

## Purpose
Docker container list port parsing: handles null Ports, string-format Ports, and dict-list Ports from docker ps --format '{{json .}}'.
## Requirements
### Requirement: Docker container list correctly parses the Ports field

`DockerContainerParser.parse_list` SHALL correctly parse the `Ports` field emitted by `docker ps --format '{{json .}}'` regardless of whether the field is a formatted string, a list of dicts, or `null`. When the `Ports` field is `null` or missing, the parser SHALL return an empty port list (no crash, no `TypeError`).

#### Scenario: Ports null treated as empty
- **WHEN** `DockerContainerParser.parse_list` receives a JSON item with `"Ports": null`
- **THEN** the parsed `ContainerInfo.ports` is an empty tuple `()`

#### Scenario: Ports string parsed via regex fallback
- **WHEN** `DockerContainerParser.parse_list` receives a JSON item with `"Ports": "0.0.0.0:8080->80/tcp"`
- **THEN** the parsed `ContainerInfo.ports` contains one `PortMapping` with `host_port=8080, container_port=80, protocol="tcp"`

#### Scenario: Ports list of dicts parsed normally
- **WHEN** `DockerContainerParser.parse_list` receives a JSON item with `"Ports": [{"IP": "0.0.0.0", "PrivatePort": 80, "PublicPort": 8080, "Type": "tcp"}]`
- **THEN** the parsed `ContainerInfo.ports` contains one `PortMapping`

