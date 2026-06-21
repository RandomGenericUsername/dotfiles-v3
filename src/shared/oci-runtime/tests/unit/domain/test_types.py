from dataclasses import fields
from pathlib import Path

import pytest

from oci_runtime.domain.enums import ContainerState, NetworkMode, RestartPolicy, VolumeMountType
from oci_runtime.domain.types import (
    BuildContext,
    ContainerInfo,
    ImageInfo,
    NetworkInfo,
    PortMapping,
    RunConfig,
    VolumeInfo,
    VolumeMount,
)


class TestVolumeMount:

    def test_required_fields(self):
        fs = {f.name: f for f in fields(VolumeMount)}
        assert fs["source"].type == str | Path
        assert fs["target"].type == str | Path
        assert fs["type"].type == VolumeMountType
        assert fs["type"].default == VolumeMountType.BIND

    def test_defaults(self):
        vm = VolumeMount(source="/src", target="/dst", type="bind")
        assert vm.read_only is False

    def test_read_only_true(self):
        vm = VolumeMount(source="/src", target="/dst", type="bind", read_only=True)
        assert vm.read_only is True

    def test_type_defaults_to_bind(self):
        vm = VolumeMount(source="/src", target="/dst")
        assert vm.type == VolumeMountType.BIND

    def test_source_and_target_accept_path(self):
        vm = VolumeMount(source=Path("/src"), target=Path("/dst"), type="volume")
        assert isinstance(vm.source, Path)
        assert isinstance(vm.target, Path)

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            VolumeMount(source="/src", target="/dst", type="invalid")


class TestPortMapping:

    def test_required_fields(self):
        fs = {f.name: f for f in fields(PortMapping)}
        assert fs["container_port"].type is int

    def test_defaults(self):
        pm = PortMapping(container_port=80)
        assert pm.host_port is None
        assert pm.protocol == "tcp"
        assert pm.host_ip == "0.0.0.0"

    def test_all_fields(self):
        pm = PortMapping(container_port=443, host_port=8443, protocol="udp", host_ip="0.0.0.0")
        assert pm.container_port == 443
        assert pm.host_port == 8443
        assert pm.protocol == "udp"
        assert pm.host_ip == "0.0.0.0"

    def test_host_port_zero(self):
        pm = PortMapping(container_port=80, host_port=0)
        assert pm.host_port == 0

    def test_host_port_none(self):
        pm = PortMapping(container_port=80)
        assert pm.host_port is None


class TestBuildContext:

    def test_defaults(self):
        ctx = BuildContext(build_file_content="FROM alpine")
        assert ctx.build_file_content == "FROM alpine"
        assert ctx.build_file_path is None
        assert ctx.context_path is None
        assert ctx.files == {}
        assert ctx.build_args == {}
        assert ctx.labels == {}
        assert ctx.target is None
        assert ctx.network is None
        assert ctx.no_cache is False
        assert ctx.pull is False
        assert ctx.rm is True
        assert ctx.build_contexts == {}

    def test_build_file_content_set(self):
        ctx = BuildContext(build_file_content="FROM alpine")
        assert ctx.build_file_content == "FROM alpine"
        assert ctx.build_file_path is None

    def test_build_file_path_set(self):
        ctx = BuildContext(build_file_path=Path("/some/Containerfile"))
        assert ctx.build_file_path == Path("/some/Containerfile")
        assert ctx.build_file_content is None

    def test_all_fields_with_content(self):
        ctx = BuildContext(
            build_file_content="FROM alpine",
            context_path=Path("/ctx"),
            files={"extra.txt": b"data"},
            build_args={"VERSION": "1.0"},
            labels={"app": "test"},
            target="stage1",
            network="host",
            no_cache=True,
            pull=True,
            rm=False,
            build_contexts={"workspace-root": "/repo"},
        )
        assert ctx.build_file_content == "FROM alpine"
        assert ctx.build_file_path is None
        assert ctx.context_path == Path("/ctx")
        assert ctx.files == {"extra.txt": b"data"}
        assert ctx.build_args == {"VERSION": "1.0"}
        assert ctx.labels == {"app": "test"}
        assert ctx.target == "stage1"
        assert ctx.network == "host"
        assert ctx.no_cache is True
        assert ctx.pull is True
        assert ctx.rm is False
        assert ctx.build_contexts == {"workspace-root": "/repo"}

    def test_all_fields_with_path(self):
        ctx = BuildContext(
            build_file_path=Path("Containerfile"),
            context_path=Path("/ctx"),
            files={"extra.txt": b"data"},
            build_args={"VERSION": "1.0"},
            labels={"app": "test"},
            target="stage1",
            network="host",
            no_cache=True,
            pull=True,
            rm=False,
            build_contexts={"workspace-root": "/repo"},
        )
        assert ctx.build_file_path == Path("Containerfile")
        assert ctx.build_file_content is None
        assert ctx.context_path == Path("/ctx")
        assert ctx.files == {"extra.txt": b"data"}
        assert ctx.build_args == {"VERSION": "1.0"}
        assert ctx.labels == {"app": "test"}
        assert ctx.target == "stage1"
        assert ctx.network == "host"
        assert ctx.no_cache is True
        assert ctx.pull is True
        assert ctx.rm is False
        assert ctx.build_contexts == {"workspace-root": "/repo"}

    def test_both_set_raises_value_error(self):
        with pytest.raises(ValueError, match="BuildContext"):
            BuildContext(build_file_content="FROM alpine", build_file_path=Path("/Dockerfile"))

    def test_neither_set_raises_value_error(self):
        with pytest.raises(ValueError, match="BuildContext"):
            BuildContext()


class TestRunConfig:

    def test_required_fields(self):
        fs = {f.name: f for f in fields(RunConfig)}
        assert fs["image"].type is str

    def test_log_driver_defaults_to_none(self):
        config = RunConfig(image="alpine")
        assert config.log_driver is None

    def test_defaults(self):
        config = RunConfig(image="alpine")
        assert config.name is None
        assert config.command is None
        assert config.entrypoint is None
        assert config.environment == {}
        assert config.volumes == []
        assert config.ports == []
        assert config.network is NetworkMode.BRIDGE
        assert config.network_container is None
        assert config.restart_policy is RestartPolicy.NO
        assert config.detach is True
        assert config.remove is False
        assert config.stream_output is False
        assert config.user is None
        assert config.working_dir is None
        assert config.hostname is None
        assert config.labels == {}
        assert config.privileged is False
        assert config.read_only is False
        assert config.memory_limit is None
        assert config.cpu_limit is None
        assert config.tty is False
        assert config.stdin_open is False
        assert config.auto_tty is False
        assert config.runtime_flags == []

    def test_volumes_list_of_volumemount(self):
        vm = VolumeMount(source="/s", target="/t", type="bind")
        config = RunConfig(image="alpine", volumes=[vm])
        assert config.volumes == [vm]

    def test_ports_list_of_portmapping(self):
        pm = PortMapping(container_port=80)
        config = RunConfig(image="alpine", ports=[pm])
        assert config.ports == [pm]

    def test_network_accepts_str(self):
        config = RunConfig(image="alpine", network="host")
        assert config.network == "host"

    def test_network_accepts_enum(self):
        config = RunConfig(image="alpine", network=NetworkMode.HOST)
        assert config.network is NetworkMode.HOST

    def test_network_container_default_none(self):
        config = RunConfig(image="alpine")
        assert config.network_container is None

    def test_network_container_accepts_string(self):
        config = RunConfig(image="alpine", network_container="nginx")
        assert config.network_container == "nginx"

    def test_restart_policy_accepts_str(self):
        config = RunConfig(image="alpine", restart_policy="always")
        assert config.restart_policy == "always"

    def test_restart_policy_accepts_enum(self):
        config = RunConfig(image="alpine", restart_policy=RestartPolicy.ALWAYS)
        assert config.restart_policy is RestartPolicy.ALWAYS

    def test_all_fields(self):
        config = RunConfig(
            image="my-image",
            name="my-container",
            command=["echo", "hello"],
            entrypoint="/bin/sh",
            environment={"ENV": "prod"},
            volumes=[VolumeMount(source="/src", target="/dst", type="bind")],
            ports=[PortMapping(container_port=80)],
            network=NetworkMode.HOST,
            network_container="nginx",
            restart_policy=RestartPolicy.ALWAYS,
            detach=False,
            remove=True,
            stream_output=True,
            user="nobody",
            working_dir="/app",
            hostname="myhost",
            labels={"app": "test"},
            log_driver=None,
            privileged=True,
            read_only=True,
            memory_limit="512m",
            cpu_limit="0.5",
            tty=True,
            stdin_open=True,
            auto_tty=True,
            runtime_flags=["--cap-drop=ALL"],
        )
        assert config.image == "my-image"
        assert config.name == "my-container"
        assert config.command == ["echo", "hello"]
        assert config.entrypoint == "/bin/sh"
        assert config.environment == {"ENV": "prod"}
        assert len(config.volumes) == 1
        assert len(config.ports) == 1
        assert config.network is NetworkMode.HOST
        assert config.network_container == "nginx"
        assert config.restart_policy is RestartPolicy.ALWAYS
        assert config.detach is False
        assert config.remove is True
        assert config.stream_output is True
        assert config.user == "nobody"
        assert config.working_dir == "/app"
        assert config.hostname == "myhost"
        assert config.labels == {"app": "test"}
        assert config.log_driver is None
        assert config.privileged is True
        assert config.read_only is True
        assert config.memory_limit == "512m"
        assert config.cpu_limit == "0.5"
        assert config.tty is True
        assert config.stdin_open is True
        assert config.auto_tty is True
        assert config.runtime_flags == ["--cap-drop=ALL"]

    def test_network_container_valid_combination(self):
        config = RunConfig(image="alpine", network=NetworkMode.CONTAINER, network_container="nginx")
        assert config.network == NetworkMode.CONTAINER
        assert config.network_container == "nginx"

    def test_network_container_without_name(self):
        config = RunConfig(image="alpine", network=NetworkMode.CONTAINER)
        assert config.network == NetworkMode.CONTAINER
        assert config.network_container is None


class TestImageInfo:

    def test_required_fields(self):
        info = ImageInfo(id="sha256:abc123")
        assert info.id == "sha256:abc123"

    def test_defaults(self):
        info = ImageInfo(id="sha256:abc123")
        assert info.tags == []
        assert info.size == 0
        assert info.created is None
        assert info.labels == {}

    def test_all_fields(self):
        info = ImageInfo(
            id="sha256:abc123",
            tags=["alpine:latest"],
            size=5000000,
            created="2024-01-01T00:00:00Z",
            labels={"maintainer": "test"},
        )
        assert info.id == "sha256:abc123"
        assert info.tags == ["alpine:latest"]
        assert info.size == 5000000
        assert info.created == "2024-01-01T00:00:00Z"
        assert info.labels == {"maintainer": "test"}


class TestContainerInfo:

    def test_state_is_typed_as_container_state(self):
        fs = {f.name: f for f in fields(ContainerInfo)}
        assert fs["state"].type is ContainerState

    def test_required_fields(self):
        info = ContainerInfo(id="abc123", name="my-container", image="alpine", state="running", status="Up 2h")
        assert info.id == "abc123"
        assert info.name == "my-container"
        assert info.image == "alpine"
        assert info.state == "running"
        assert info.status == "Up 2h"

    def test_defaults(self):
        info = ContainerInfo(id="abc", name="c1", image="alpine", state="running", status="Up 2h")
        assert info.created is None
        assert info.ports == []
        assert info.labels == {}
        assert info.exit_code is None

    def test_all_fields(self):
        info = ContainerInfo(
            id="abc123",
            name="c1",
            image="alpine",
            state="exited",
            status="Exited (0) 1h ago",
            created="2024-01-01T00:00:00Z",
            ports=[PortMapping(container_port=80)],
            labels={"app": "test"},
            exit_code=0,
        )
        assert info.id == "abc123"
        assert info.name == "c1"
        assert info.image == "alpine"
        assert info.state == "exited"
        assert info.status == "Exited (0) 1h ago"
        assert info.created == "2024-01-01T00:00:00Z"
        assert len(info.ports) == 1
        assert info.labels == {"app": "test"}
        assert info.exit_code == 0


class TestVolumeInfo:

    def test_required_fields(self):
        info = VolumeInfo(name="my-vol", driver="local")
        assert info.name == "my-vol"
        assert info.driver == "local"

    def test_defaults(self):
        info = VolumeInfo(name="my-vol", driver="local")
        assert info.mountpoint is None
        assert info.labels == {}

    def test_all_fields(self):
        info = VolumeInfo(name="my-vol", driver="local", mountpoint="/mnt/data", labels={"app": "test"})
        assert info.name == "my-vol"
        assert info.driver == "local"
        assert info.mountpoint == "/mnt/data"
        assert info.labels == {"app": "test"}


class TestNetworkInfo:

    def test_required_fields(self):
        info = NetworkInfo(id="net1", name="bridge", driver="bridge", scope="local")
        assert info.id == "net1"
        assert info.name == "bridge"
        assert info.driver == "bridge"
        assert info.scope == "local"

    def test_defaults(self):
        info = NetworkInfo(id="net1", name="bridge", driver="bridge", scope="local")
        assert info.labels == {}

    def test_all_fields(self):
        info = NetworkInfo(id="net1", name="host", driver="host", scope="local", labels={"app": "test"})
        assert info.id == "net1"
        assert info.name == "host"
        assert info.driver == "host"
        assert info.scope == "local"
        assert info.labels == {"app": "test"}
