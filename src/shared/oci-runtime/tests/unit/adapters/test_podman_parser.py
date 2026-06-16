import pytest

from oci_runtime.ports.parsers import ParsingError
from oci_runtime.adapters.parser.podman import (
    PodmanContainerParser,
    PodmanImageParser,
    PodmanNetworkParser,
    PodmanVolumeParser,
)

PODMAN_CONTAINER_INSPECT = """[
  {
    "Id": "xyz789ghi012",
    "Name": "my-podman-container",
    "Config": {"Image": "alpine:latest"},
    "State": {"Status": "running", "ExitCode": 0, "Running": true},
    "Created": "2024-06-15T00:00:00Z",
    "HostConfig": {},
    "NetworkSettings": {
      "Ports": {}
    }
  }
]"""

PODMAN_CONTAINER_INSPECT_WITH_PORTS = """[
  {
    "Id": "abc123def456",
    "Name": "web-server",
    "Config": {"Image": "nginx:latest"},
    "State": {"Status": "running", "ExitCode": 0, "Running": true},
    "Created": "2024-06-15T10:00:00Z",
    "HostConfig": {},
    "NetworkSettings": {
      "Ports": {
        "80/tcp": [
          {
            "HostIp": "0.0.0.0",
            "HostPort": "8080"
          }
        ],
        "443/tcp": [
          {
            "HostIp": "127.0.0.1",
            "HostPort": "8443"
          }
        ]
      }
    }
  }
]"""

PODMAN_CONTAINER_INSPECT_MULTI_PORTS = """[
  {
    "Id": "multi789xyz",
    "Name": "app-server",
    "Config": {"Image": "app:latest"},
    "State": {"Status": "running", "ExitCode": 0},
    "Created": "2024-06-15T12:00:00Z",
    "HostConfig": {},
    "NetworkSettings": {
      "Ports": {
        "3000/tcp": [
          {
            "HostIp": "0.0.0.0",
            "HostPort": "3000"
          },
          {
            "HostIp": "127.0.0.1",
            "HostPort": "13000"
          }
        ],
        "5000/udp": [
          {
            "HostIp": "0.0.0.0",
            "HostPort": "5000"
          }
        ]
      }
    }
  }
]"""

PODMAN_CONTAINER_LIST = """[
  {
    "Id": "xyz789",
    "Names": ["/pc1"],
    "Image": "alpine",
    "ImageID": "sha256:yyy",
    "State": "running",
    "Status": "Up 1h",
    "Created": 1718496000,
    "Ports": [],
    "Labels": {}
  }
]"""

PODMAN_CONTAINER_LIST_WITH_PORTS = """[
  {
    "Id": "port789abc",
    "Names": ["/web-server"],
    "Image": "nginx",
    "ImageID": "sha256:xxx",
    "State": "running",
    "Status": "Up 2h",
    "Created": 1718496000,
    "Ports": [
      {"HostPort": 8080, "ContainerPort": 80, "Protocol": "tcp", "HostIp": "0.0.0.0", "Range": 1},
      {"HostPort": 8443, "ContainerPort": 443, "Protocol": "tcp", "HostIp": "127.0.0.1", "Range": 1}
    ],
    "Labels": {}
  }
]"""

PODMAN_IMAGE_INSPECT = """[
  {
    "Id": "sha256:xyz789ghi012",
    "RepoTags": ["alpine:latest"],
    "Size": 5000000,
    "Created": "2024-06-15T00:00:00Z",
    "Labels": {}
  }
]"""

PODMAN_IMAGE_LIST = """[
  {
    "Id": "sha256:xyz789",
    "RepoTags": ["alpine:latest"],
    "Size": 5000000,
    "Created": 1718496000,
    "Labels": {}
  }
]"""

PODMAN_VOLUME_INSPECT = """[
  {
    "Name": "podman-vol",
    "Driver": "local",
    "Mountpoint": "/home/user/.local/share/containers/storage/volumes/podman-vol/_data",
    "Labels": {},
    "Scope": "local"
  }
]"""

PODMAN_VOLUME_LIST = """[
  {
    "Name": "podman-vol",
    "Driver": "local",
    "Mountpoint": "/home/user/.local/share/containers/storage/volumes/podman-vol/_data",
    "Labels": {}
  }
]"""

PODMAN_NETWORK_INSPECT = """[
  {
    "Id": "podnet123",
    "Name": "podman-net",
    "Driver": "bridge",
    "Scope": "local",
    "Labels": {}
  }
]"""

PODMAN_NETWORK_LIST = """[
  {
    "Id": "podnet123",
    "Name": "podman-net",
    "Driver": "bridge",
    "Scope": "local",
    "Labels": {}
  }
]"""


class TestPodmanContainerParser:
    def setup_method(self):
        self.parser = PodmanContainerParser()

    def test_parse_inspect(self):
        info = self.parser.parse_inspect(PODMAN_CONTAINER_INSPECT)
        assert info.id == "xyz789ghi012"
        assert info.name == "my-podman-container"
        assert info.image == "alpine:latest"
        assert info.state == "running"
        assert info.created == "2024-06-15T00:00:00Z"

    def test_parse_list(self):
        infos = self.parser.parse_list(PODMAN_CONTAINER_LIST)
        assert len(infos) == 1
        assert infos[0].id == "xyz789"
        assert infos[0].state == "running"

    def test_parse_list_with_ports(self):
        infos = self.parser.parse_list(PODMAN_CONTAINER_LIST_WITH_PORTS)
        assert len(infos) == 1
        assert infos[0].id == "port789abc"
        assert len(infos[0].ports) == 2
        assert infos[0].ports[0].container_port == 80
        assert infos[0].ports[0].host_port == 8080
        assert infos[0].ports[0].protocol == "tcp"
        assert infos[0].ports[0].host_ip == "0.0.0.0"
        assert infos[0].ports[1].container_port == 443
        assert infos[0].ports[1].host_port == 8443
        assert infos[0].ports[1].protocol == "tcp"
        assert infos[0].ports[1].host_ip == "127.0.0.1"

    def test_is_not_found_error(self):
        assert self.parser.is_not_found_error("no such container")
        assert not self.parser.is_not_found_error("something else")

    def test_parse_list_missing_names_raises(self):
        with pytest.raises(ParsingError, match="Names"):
            self.parser.parse_list('[{"Id": "abc", "Names": null}]')

    def test_parse_list_names_empty_raises(self):
        with pytest.raises(ParsingError, match="Names"):
            self.parser.parse_list('[{"Id": "abc", "Names": []}]')

    def test_parse_inspect_with_single_port(self):
       """Unit test for Podman port parsing with single mapped port."""
       info = self.parser.parse_inspect(PODMAN_CONTAINER_INSPECT_WITH_PORTS)
       assert info.id == "abc123def456"
       assert info.name == "web-server"
       assert len(info.ports) == 2
        
       # First port: 80/tcp -> 8080
       assert info.ports[0].container_port == 80
       assert info.ports[0].host_port == 8080
       assert info.ports[0].protocol == "tcp"
       assert info.ports[0].host_ip == "0.0.0.0"
        
       # Second port: 443/tcp -> 8443 on localhost
       assert info.ports[1].container_port == 443
       assert info.ports[1].host_port == 8443
       assert info.ports[1].protocol == "tcp"
       assert info.ports[1].host_ip == "127.0.0.1"

    def test_parse_inspect_with_multiple_bindings_per_port(self):
       """Unit test for Podman port parsing with multiple bindings per container port."""
       info = self.parser.parse_inspect(PODMAN_CONTAINER_INSPECT_MULTI_PORTS)
       assert info.id == "multi789xyz"
       assert info.name == "app-server"
       # Should have 3 port mappings: 3000/tcp (2 bindings) + 5000/udp (1 binding)
       assert len(info.ports) == 3
        
       # Find the TCP port
       tcp_ports = [p for p in info.ports if p.protocol == "tcp"]
       assert len(tcp_ports) == 2
       assert all(p.container_port == 3000 for p in tcp_ports)
       assert {p.host_port for p in tcp_ports} == {3000, 13000}
        
       # Find the UDP port
       udp_ports = [p for p in info.ports if p.protocol == "udp"]
       assert len(udp_ports) == 1
       assert udp_ports[0].container_port == 5000
       assert udp_ports[0].host_port == 5000

    def test_parse_inspect_empty_ports(self):
       """Unit test for Podman port parsing with no port mappings."""
       info = self.parser.parse_inspect(PODMAN_CONTAINER_INSPECT)
       assert info.id == "xyz789ghi012"
       assert len(info.ports) == 0


class TestPodmanImageParser:
    def setup_method(self):
        self.parser = PodmanImageParser()

    def test_parse_inspect(self):
        info = self.parser.parse_inspect(PODMAN_IMAGE_INSPECT)
        assert "xyz789ghi012" in info.id
        assert info.tags == ["alpine:latest"]
        assert info.size == 5000000

    def test_parse_list(self):
        infos = self.parser.parse_list(PODMAN_IMAGE_LIST)
        assert len(infos) == 1

    def test_is_not_found_error(self):
        assert self.parser.is_not_found_error("image not found")
        assert not self.parser.is_not_found_error("something else")

    def test_parse_build_output_without_prefix(self):
        image_id = self.parser.parse_build_output("abc123def456\n")
        assert image_id == "sha256:abc123def456"

    def test_parse_build_output_with_prefix(self):
        image_id = self.parser.parse_build_output("sha256:abc123def456\n")
        assert image_id == "sha256:abc123def456"


class TestPodmanVolumeParser:
    def setup_method(self):
        self.parser = PodmanVolumeParser()

    def test_parse_inspect(self):
        info = self.parser.parse_inspect(PODMAN_VOLUME_INSPECT)
        assert info.name == "podman-vol"
        assert info.driver == "local"

    def test_parse_list(self):
        infos = self.parser.parse_list(PODMAN_VOLUME_LIST)
        assert len(infos) == 1

    def test_is_not_found_error(self):
        assert self.parser.is_not_found_error("no such volume")
        assert not self.parser.is_not_found_error("something else")


class TestPodmanNetworkParser:
    def setup_method(self):
        self.parser = PodmanNetworkParser()

    def test_parse_inspect(self):
        info = self.parser.parse_inspect(PODMAN_NETWORK_INSPECT)
        assert info.id == "podnet123"
        assert info.name == "podman-net"
        assert info.driver == "bridge"
        assert info.scope == "local"

    def test_parse_list(self):
        infos = self.parser.parse_list(PODMAN_NETWORK_LIST)
        assert len(infos) == 1

    def test_is_not_found_error(self):
        assert self.parser.is_not_found_error("no such network")
        assert not self.parser.is_not_found_error("something else")


class TestPodmanImageParserNormalization:
    def setup_method(self):
        self.parser = PodmanImageParser()

    def test_parse_list_null_repo_tags(self):
        data = '[{"Id":"sha256:abc","RepoTags":null,"Size":5000000,"Labels":{}}]'
        result = self.parser.parse_list(data)
        assert len(result) == 1
        assert result[0].tags == []

    def test_parse_list_names_fallback(self):
        data = '[{"Id":"sha256:abc","Names":["alpine:latest"],"Size":5000000,"Labels":{}}]'
        result = self.parser.parse_list(data)
        assert len(result) == 1
        assert result[0].tags == ["alpine:latest"]


class TestPodmanNetworkParserNormalization:
    def setup_method(self):
        self.parser = PodmanNetworkParser()

    def test_parse_list_lowercase_network_keys(self):
        data = '[{"id":"2f259bab93aa","name":"podman","driver":"bridge","labels":{}}]'
        result = self.parser.parse_list(data)
        assert len(result) == 1
        assert result[0].id == "2f259bab93aa"
        assert result[0].name == "podman"
        assert result[0].driver == "bridge"


class TestPodmanVolumeParserNormalization:
    def setup_method(self):
        self.parser = PodmanVolumeParser()

    def test_parse_list_labels_string_to_dict(self):
        data = '[{"Name":"my-vol","Driver":"local","Mountpoint":"/data","Labels":""}]'
        result = self.parser.parse_list(data)
        assert len(result) == 1
        assert result[0].name == "my-vol"
        assert result[0].labels == {}
