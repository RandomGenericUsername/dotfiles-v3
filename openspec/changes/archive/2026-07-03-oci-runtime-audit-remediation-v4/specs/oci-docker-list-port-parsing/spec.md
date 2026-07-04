## ADDED Requirements

### Requirement: Docker list parser handles the Ports field as a formatted string

`DockerContainerParser.parse_list` SHALL handle the `Ports` field emitted by `docker ps --format '{{json .}}'`, which is a **pre-formatted string** (e.g. `"0.0.0.0:49154->27017/tcp"`) and NOT a list of dicts. When `item["Ports"]` is a `str`, the parser SHALL parse it with a regex (`(\S*):?(\d+)->(\d+)/(tcp|udp|sctp)`, plus a bare-exposed form `(\d+)/(tcp|udp|sctp)`) into `PortMapping` objects. When `item["Ports"]` is a `list`, the existing dict-based parsing is preserved. The parser MUST NOT raise `AttributeError` on real `docker ps` output containing published ports.

#### Scenario: parse_list does not crash on real docker ps output with published ports
- **WHEN** `DockerContainerParser().parse_list(json.dumps({"ID":"abc","Image":"nginx","Names":"web","Ports":"0.0.0.0:49154->27017/tcp","Status":"Up"}))` is called
- **THEN** it returns a list of one `ContainerInfo` whose `ports` contains a `PortMapping(container_port=27017, host_port=49154, host_ip="0.0.0.0", protocol="tcp")`

#### Scenario: parse_list handles a bare exposed port string
- **WHEN** `parse_list` receives an item whose `Ports` is `"80/tcp"`
- **THEN** the resulting `ContainerInfo.ports` contains `PortMapping(container_port=80, host_port=None, host_ip=None, protocol="tcp")`

#### Scenario: parse_list still handles the legacy list-of-dicts shape
- **WHEN** `parse_list` receives an item whose `Ports` is `[{"PrivatePort": 80, "PublicPort": 8080, "Type": "tcp", "HostIp": "0.0.0.0"}]`
- **THEN** the resulting `ContainerInfo.ports` contains `PortMapping(container_port=80, host_port=8080, host_ip="0.0.0.0", protocol="tcp")`

#### Scenario: empty Ports string yields no ports
- **WHEN** `parse_list` receives an item whose `Ports` is `""`
- **THEN** the resulting `ContainerInfo.ports` is an empty tuple and no exception is raised
