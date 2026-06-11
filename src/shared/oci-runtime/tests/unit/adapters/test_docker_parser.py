from oci_runtime.adapters.parser.docker import (
    DockerContainerParser,
    DockerImageParser,
    DockerNetworkParser,
    DockerVolumeParser,
)

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

    def test_parse_empty_inspect(self):
        info = self.parser.parse_inspect("[]")
        assert info is None or info.id == ""

    def test_parse_malformed(self):
        info = self.parser.parse_inspect("not json")
        assert info is None


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

    def test_parse_build_output(self):
        image_id = self.parser.parse_build_output("sha256:abc123def456\n")
        assert image_id == "abc123def456"

    def test_parse_empty_inspect(self):
        info = self.parser.parse_inspect("[]")
        assert info is None or info.id == ""


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
