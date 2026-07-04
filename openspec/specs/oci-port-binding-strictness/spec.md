# Port Binding Strictness

## Purpose

Ensures PortMapping.host_ip is honored in container run -p flags and that Docker inspect parser preserves the CLI truth for empty vs. explicit 0.0.0.0 HostIp.

## Requirements

### Requirement: PortMapping.host_ip honored in container run

`CliContainerManager.run()` must emit `-p` flags that include `PortMapping.host_ip` when it is not `None`. The four valid combinations are:

- `host_ip=None, host_port=None` → `-p <container_port>/<protocol>`
- `host_ip=None, host_port=8080` → `-p 8080:80/tcp`
- `host_ip="127.0.0.1", host_port=None` → `-p 127.0.0.1::80/tcp` (ephemeral host port, loopback bind)
- `host_ip="127.0.0.1", host_port=8080` → `-p 127.0.0.1:8080:80/tcp`
- `host_ip="0.0.0.0", host_port=8080` → `-p 0.0.0.0:8080:80/tcp` (explicit all-interfaces bind)

The Docker inspect parser must preserve the CLI truth:
- When `docker inspect` emits `HostIp: ""` (empty) → `PortMapping.host_ip = None` (unbound)
- When `docker inspect` emits `HostIp: "0.0.0.0"` → `PortMapping.host_ip = "0.0.0.0"` (explicit all-interfaces bind)

#### Scenario: Loopback-only binding is preserved end-to-end
- **WHEN** `RunConfig` specifies `PortMapping(container_port=80, host_port=8080, host_ip="127.0.0.1")`
- **THEN** `CliContainerManager.run()` emits `-p 127.0.0.1:8080:80/tcp` in the docker command

#### Scenario: Explicit all-interfaces bind is preserved
- **WHEN** `RunConfig` specifies `PortMapping(container_port=80, host_port=8080, host_ip="0.0.0.0")`
- **THEN** `CliContainerManager.run()` emits `-p 0.0.0.0:8080:80/tcp` (not `-p 8080:80/tcp`)

#### Scenario: Unbound port has no IP prefix
- **WHEN** `RunConfig` specifies `PortMapping(container_port=80, host_port=8080, host_ip=None)`
- **THEN** `CliContainerManager.run()` emits `-p 8080:80/tcp`

#### Scenario: Docker inspect empty HostIp maps to host_ip=None
- **WHEN** `DockerContainerParser.parse_inspect()` is fed real `docker inspect` output where `HostIp` is empty string
- **THEN** the resulting `PortMapping.host_ip` is `None`

#### Scenario: Docker inspect explicit 0.0.0.0 HostIp maps to host_ip="0.0.0.0"
- **WHEN** `DockerContainerParser.parse_inspect()` is fed real output where `HostIp: "0.0.0.0"`
- **THEN** the resulting `PortMapping.host_ip` is `"0.0.0.0"`

#### Scenario: Podman inspect empty HostIp maps to host_ip=None
- **WHEN** `PodmanContainerParser.parse_inspect()` is fed real `podman inspect` output where `HostIp` is empty/missing
- **THEN** the resulting `PortMapping.host_ip` is `None`