import pytest

from oci_runtime.adapters.parser.docker import (
    DockerContainerParser,
    DockerImageParser,
    DockerNetworkParser,
    DockerVolumeParser,
)
from oci_runtime.adapters.parser.exceptions import ParsingError

DOCKER_CONTAINER_INSPECT = """[
  {
    "Id": "abc123def456",
    "Name": "/my-container",
    "Config": {"Image": "alpine:latest"},
    "State": {"Status": "running", "ExitCode": 0, "Running": true},
    "Created": "2024-01-01T00:00:00Z",
    "HostConfig": {},
    "NetworkSettings": {
      "Ports": {
        "80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]
      }
    }
  }
]"""

DOCKER_CONTAINER_LIST = """[
  {
    "Id": "abc123",
    "Names": ["/c1"],
    "Image": "alpine",
    "ImageID": "sha256:xxx",
    "State": "running",
    "Status": "Up 2h",
    "Created": 1704067200,
    "Ports": [{"PrivatePort": 80, "PublicPort": 8080, "Type": "tcp"}],
    "Labels": {"app": "test"}
  }
]"""

DOCKER_IMAGE_INSPECT = """[
  {
    "Id": "sha256:abc123def456",
    "RepoTags": ["alpine:latest"],
    "Size": 5000000,
    "Created": "2024-01-01T00:00:00Z",
    "Labels": {"maintainer": "test"}
  }
]"""

DOCKER_IMAGE_LIST = """[
  {
    "Id": "sha256:abc123",
    "RepoTags": ["alpine:latest"],
    "Size": 5000000,
    "Created": 1704067200,
    "Labels": {"maintainer": "test"}
  }
]"""

DOCKER_VOLUME_INSPECT = """[
  {
    "Name": "my-vol",
    "Driver": "local",
    "Mountpoint": "/var/lib/docker/volumes/my-vol/_data",
    "Labels": {"app": "test"},
    "Scope": "local"
  }
]"""

DOCKER_VOLUME_LIST = """[
  {
    "Name": "my-vol",
    "Driver": "local",
    "Mountpoint": "/var/lib/docker/volumes/my-vol/_data",
    "Labels": {"app": "test"}
  }
]"""

DOCKER_NETWORK_INSPECT = """[
  {
    "Id": "net123",
    "Name": "bridge",
    "Driver": "bridge",
    "Scope": "local",
    "Labels": {"app": "test"}
  }
]"""

DOCKER_NETWORK_LIST = """[
  {
    "Id": "net123",
    "Name": "bridge",
    "Driver": "bridge",
    "Scope": "local",
    "Labels": {"app": "test"}
  }
]"""


class TestDockerPortParsing:
    def test_parse_docker_ports_non_numeric_key(self):
        from oci_runtime.adapters.parser.docker import _parse_docker_ports
        item = {
            "NetworkSettings": {
                "Ports": {
                    "abc/tcp": [{"HostPort": "8080", "HostIp": "0.0.0.0"}],
                }
            }
        }
        ports = _parse_docker_ports(item)
        assert ports == []

    def test_parse_docker_ports_missing_slash(self):
        from oci_runtime.adapters.parser.docker import _parse_docker_ports
        item = {
            "NetworkSettings": {
                "Ports": {
                    "abc": [{"HostPort": "8080", "HostIp": "0.0.0.0"}],
                }
            }
        }
        ports = _parse_docker_ports(item)
        assert ports == []

    def test_parse_docker_ports_valid_ports_still_work(self):
        from oci_runtime.adapters.parser.docker import _parse_docker_ports
        item = {
            "NetworkSettings": {
                "Ports": {
                    "80/tcp": [{"HostPort": "8080", "HostIp": "0.0.0.0"}],
                    "443/udp": [{"HostPort": "8443", "HostIp": "127.0.0.1"}],
                }
            }
        }
        ports = _parse_docker_ports(item)
        assert len(ports) == 2
        assert ports[0].container_port == 80
        assert ports[0].host_port == 8080
        assert ports[1].container_port == 443
        assert ports[1].protocol == "udp"


class TestDockerContainerParser:
    def setup_method(self):
        self.parser = DockerContainerParser()

    def test_parse_inspect(self):
        info = self.parser.parse_inspect(DOCKER_CONTAINER_INSPECT)
        assert info.id == "abc123def456"
        assert info.name == "my-container"
        assert info.image == "alpine:latest"
        assert info.state == "running"
        assert info.status == "running"
        assert info.created == "2024-01-01T00:00:00Z"
        assert len(info.ports) == 1
        assert info.ports[0].container_port == 80
        assert info.ports[0].host_port == 8080

    def test_parse_list(self):
        infos = self.parser.parse_list(DOCKER_CONTAINER_LIST)
        assert len(infos) == 1
        assert infos[0].id == "abc123"
        assert infos[0].name == "c1"
        assert infos[0].image == "alpine"
        assert infos[0].state == "running"

    def test_is_not_found_error(self):
        assert self.parser.is_not_found_error("No such container: abc")
        assert not self.parser.is_not_found_error("something else")

    def test_parse_empty_inspect_raises(self):
        with pytest.raises(ParsingError):
            self.parser.parse_inspect("[]")

    def test_parse_malformed_raises(self):
        with pytest.raises(ParsingError):
            self.parser.parse_inspect("not json")

    def test_parse_list_missing_names_raises(self):
        with pytest.raises(ParsingError, match="Names"):
            self.parser.parse_list('[{"Id": "abc", "Names": null}]')

    def test_parse_list_names_empty_raises(self):
        with pytest.raises(ParsingError, match="Names"):
            self.parser.parse_list('[{"Id": "abc", "Names": []}]')


class TestDockerImageParser:
    def setup_method(self):
        self.parser = DockerImageParser()

    def test_parse_inspect(self):
        info = self.parser.parse_inspect(DOCKER_IMAGE_INSPECT)
        assert "abc123def456" in info.id
        assert info.tags == ["alpine:latest"]
        assert info.size == 5000000
        assert info.created is not None
        assert info.labels == {"maintainer": "test"}

    def test_parse_list(self):
        infos = self.parser.parse_list(DOCKER_IMAGE_LIST)
        assert len(infos) == 1
        assert infos[0].tags == ["alpine:latest"]

    def test_is_not_found_error(self):
        assert self.parser.is_not_found_error("No such image: alpine")
        assert self.parser.is_not_found_error("pull access denied")
        assert not self.parser.is_not_found_error("something else")

    def test_parse_build_output_with_prefix(self):
        image_id = self.parser.parse_build_output("sha256:abc123def456\n")
        assert image_id == "sha256:abc123def456"

    def test_parse_build_output_without_prefix(self):
        image_id = self.parser.parse_build_output("abc123def456\n")
        assert image_id == "sha256:abc123def456"

    def test_parse_empty_inspect_raises(self):
        with pytest.raises(ParsingError):
            self.parser.parse_inspect("[]")


class TestDockerVolumeParser:
    def setup_method(self):
        self.parser = DockerVolumeParser()

    def test_parse_inspect(self):
        info = self.parser.parse_inspect(DOCKER_VOLUME_INSPECT)
        assert info.name == "my-vol"
        assert info.driver == "local"
        assert info.mountpoint is not None
        assert info.labels == {"app": "test"}

    def test_parse_list(self):
        infos = self.parser.parse_list(DOCKER_VOLUME_LIST)
        assert len(infos) == 1
        assert infos[0].name == "my-vol"

    def test_is_not_found_error(self):
        assert self.parser.is_not_found_error("No such volume: my-vol")
        assert not self.parser.is_not_found_error("something else")


class TestDockerNetworkParser:
    def setup_method(self):
        self.parser = DockerNetworkParser()

    def test_parse_inspect(self):
        info = self.parser.parse_inspect(DOCKER_NETWORK_INSPECT)
        assert info.id == "net123"
        assert info.name == "bridge"
        assert info.driver == "bridge"
        assert info.scope == "local"
        assert info.labels == {"app": "test"}

    def test_parse_list(self):
        infos = self.parser.parse_list(DOCKER_NETWORK_LIST)
        assert len(infos) == 1
        assert infos[0].name == "bridge"

    def test_is_not_found_error(self):
        assert self.parser.is_not_found_error("No such network: net1")
        assert not self.parser.is_not_found_error("something else")


class TestDockerImageParserNDJSON:
    def setup_method(self):
        self.parser = DockerImageParser()

    def test_parse_list_ndjson_image(self):
        ndjson = '{"ID":"sha256:abc","Repository":"alpine","Tag":"latest","VirtualSize":"8.454MB","Created":1704067200,"Labels":""}\n{"ID":"sha256:def","Repository":"ubuntu","Tag":"22.04","VirtualSize":"1.5GB","Created":1704067201,"Labels":{"os":"linux"}}'
        result = self.parser.parse_list(ndjson)
        assert len(result) == 2
        assert "sha256:abc" in result[0].id
        assert result[0].tags == ["alpine:latest"]
        assert isinstance(result[0].size, int)
        assert result[0].size > 0
        assert result[0].labels == {}
        assert "sha256:def" in result[1].id
        assert result[1].tags == ["ubuntu:22.04"]
        assert result[1].labels == {"os": "linux"}

    def test_parse_list_docker_ls_keys(self):
        ndjson = '{"ID":"sha256:abc","Repository":"alpine","Tag":"latest","VirtualSize":"8847360","Labels":""}'
        result = self.parser.parse_list(ndjson)
        assert len(result) == 1
        assert result[0].tags == ["alpine:latest"]

    def test_parse_list_labels_string_to_dict(self):
        ndjson = '{"ID":"sha256:abc","Labels":""}'
        result = self.parser.parse_list(ndjson)
        assert result[0].labels == {}

    def test_parse_list_size_as_string(self):
        ndjson = '{"ID":"sha256:abc","VirtualSize":"8847360","Labels":{}}'
        result = self.parser.parse_list(ndjson)
        assert isinstance(result[0].size, int)


class TestDockerNetworkParserNDJSON:
    def setup_method(self):
        self.parser = DockerNetworkParser()

    def test_parse_list_ndjson_network(self):
        ndjson = '{"ID":"11de959545c4","Name":"bridge","Driver":"bridge","Scope":"local","Labels":""}\n{"ID":"8d7e2f0997be","Name":"host","Driver":"host","Scope":"local","Labels":""}'
        result = self.parser.parse_list(ndjson)
        assert len(result) == 2
        assert "11de959545c4" in result[0].id
        assert result[0].name == "bridge"
        assert result[0].driver == "bridge"
        assert result[1].name == "host"


class TestDockerVolumeParserNDJSON:
    def setup_method(self):
        self.parser = DockerVolumeParser()

    def test_parse_list_labels_string_to_dict(self):
        ndjson = '{"Name":"my-vol","Driver":"local","Mountpoint":"/data","Labels":""}'
        result = self.parser.parse_list(ndjson)
        assert len(result) == 1
        assert result[0].name == "my-vol"
        assert result[0].labels == {}
