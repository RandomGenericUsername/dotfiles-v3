## ADDED Requirements

### Requirement: Podman inspect preserves HostIp-only port bindings

`PodmanContainerParser._parse_ports` (inspect path) SHALL append a `PortMapping` for every binding entry, including those that have `HostIp` set but no `HostPort` (Podman random/ephemeral host-port bindings, `--publish 8080` style yielding `HostPort: 0`). When `HostPort` is empty/missing/zero, `PortMapping.host_port` is `None`; the binding is NOT dropped. This mirrors the Docker inspect parser, which appends unconditionally, so the two runtimes return the same `PortMapping` shape for the same input.

#### Scenario: Podman binding with HostIp but no HostPort is preserved
- **WHEN** `PodmanContainerParser().parse_inspect('{"NetworkSettings":{"Ports":{"80/tcp":[{"HostIp":"127.0.0.1"}]}}}')` is called
- **THEN** the resulting `ContainerInfo.ports` contains `PortMapping(container_port=80, host_port=None, host_ip="127.0.0.1", protocol="tcp")`

#### Scenario: Podman binding with HostPort=0 is preserved as host_port=None
- **WHEN** `parse_inspect` receives a binding `{"HostIp":"0.0.0.0","HostPort":"0"}`
- **THEN** the resulting `PortMapping` has `host_port=None` (not dropped) and `host_ip="0.0.0.0"`

#### Scenario: Docker and Podman produce equivalent ports for the same binding
- **WHEN** the same `{"80/tcp":[{"HostIp":"127.0.0.1"}]}` input is parsed by both `DockerContainerParser` and `PodmanContainerParser`
- **THEN** the resulting `PortMapping` tuples are equal
