from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from types import MappingProxyType

import pytest

from oci_runtime.domain.enums import (
    ContainerState,
    NetworkMode,
    RestartPolicy,
    VolumeMountType,
)
from oci_runtime.domain.types import (
    BuildContext,
    ContainerInfo,
    ExecResult,
    ImageInfo,
    NetworkInfo,
    PortMapping,
    RawExecResult,
    RunConfig,
    VolumeInfo,
    VolumeMount,
)


class TestVolumeMount:
    def test_required_fields(self):
        fs = {f.name: f for f in fields(VolumeMount)}
        assert fs["source"].type == str | Path | None
        assert fs["target"].type == str | Path
        assert fs["type"].type == VolumeMountType
        assert fs["type"].default == VolumeMountType.BIND

    def test_defaults(self):
        vm = VolumeMount(source="/src", target="/dst", type=VolumeMountType.BIND)
        assert vm.read_only is False

    def test_read_only_true(self):
        vm = VolumeMount(
            source="/src", target="/dst", type=VolumeMountType.BIND, read_only=True
        )
        assert vm.read_only is True

    def test_type_defaults_to_bind(self):
        vm = VolumeMount(source="/src", target="/dst")
        assert vm.type == VolumeMountType.BIND

    def test_source_and_target_accept_path(self):
        vm = VolumeMount(
            source=Path("/src"), target=Path("/dst"), type=VolumeMountType.VOLUME
        )
        assert isinstance(vm.source, Path)
        assert isinstance(vm.target, Path)

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError):
            VolumeMount(source="/src", target="/dst", type="invalid")

    def test_non_tmpfs_requires_source(self):
        with pytest.raises(ValueError, match="non-TMPFS"):
            VolumeMount(source=None, target="/t", type=VolumeMountType.BIND)

    def test_tmpfs_allows_source_none(self):
        vm = VolumeMount(source=None, target="/tmpfs", type=VolumeMountType.TMPFS)
        assert vm.source is None
        assert vm.target == "/tmpfs"
        assert vm.type is VolumeMountType.TMPFS


class TestPortMapping:
    def test_required_fields(self):
        fs = {f.name: f for f in fields(PortMapping)}
        assert fs["container_port"].type is int

    def test_defaults(self):
        pm = PortMapping(container_port=80, host_ip=None)
        assert pm.host_port is None
        assert pm.protocol == "tcp"
        assert pm.host_ip is None

    def test_all_fields(self):
        pm = PortMapping(
            container_port=443, host_port=8443, protocol="udp", host_ip="0.0.0.0"
        )
        assert pm.container_port == 443
        assert pm.host_port == 8443
        assert pm.protocol == "udp"
        assert pm.host_ip == "0.0.0.0"

    def test_host_port_zero(self):
        pm = PortMapping(container_port=80, host_port=0, host_ip="0.0.0.0")
        assert pm.host_port == 0

    def test_host_port_none(self):
        pm = PortMapping(container_port=80, host_ip=None)
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
        assert ctx.files == {}
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
        assert ctx.files == {}
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
            BuildContext(
                build_file_content="FROM alpine", build_file_path=Path("/Dockerfile")
            )

    def test_neither_set_raises_value_error(self):
        with pytest.raises(ValueError, match="BuildContext"):
            BuildContext()

    def test_build_context_forbids_path_and_files(self):
        from pathlib import Path

        with pytest.raises(ValueError, match="context_path"):
            BuildContext(
                build_file_content="FROM alpine",
                context_path=Path("/x"),
                files={"a": b"x"},
            )


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
        assert config.volumes == ()
        assert config.ports == ()
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
        assert config.runtime_flags == ()

    def test_volumes_list_of_volumemount(self):
        vm = VolumeMount(source="/s", target="/t", type=VolumeMountType.BIND)
        config = RunConfig(image="alpine", volumes=[vm])
        assert config.volumes == (vm,)

    def test_ports_list_of_portmapping(self):
        pm = PortMapping(container_port=80, host_ip=None)
        config = RunConfig(image="alpine", ports=[pm])
        assert config.ports == (pm,)

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
            volumes=[
                VolumeMount(source="/src", target="/dst", type=VolumeMountType.BIND)
            ],
            ports=[PortMapping(container_port=80, host_ip=None)],
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
        assert config.command == ("echo", "hello")
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
        assert config.runtime_flags == ("--cap-drop=ALL",)

    def test_network_container_valid_combination(self):
        config = RunConfig(
            image="alpine", network=NetworkMode.CONTAINER, network_container="nginx"
        )
        assert config.network == NetworkMode.CONTAINER
        assert config.network_container == "nginx"

    def test_network_container_without_name(self):
        with pytest.raises(
            ValueError, match="network=CONTAINER requires network_container"
        ):
            RunConfig(image="alpine", network=NetworkMode.CONTAINER)

    def test_runconfig_network_container_requires_arg(self):
        with pytest.raises(
            ValueError, match="network=CONTAINER requires network_container"
        ):
            RunConfig(image="alpine", network=NetworkMode.CONTAINER)

    def test_runconfig_detach_tty_mutually_exclusive(self):
        with pytest.raises(
            ValueError, match="detach=True is mutually exclusive with tty/auto_tty"
        ):
            RunConfig(image="alpine", detach=True, tty=True)

    def test_runconfig_invalid_memory_limit_raises(self):
        with pytest.raises(ValueError):
            RunConfig(image="x", memory_limit="notalimit")

    def test_runconfig_invalid_cpu_limit_raises(self):
        with pytest.raises(ValueError):
            RunConfig(image="x", cpu_limit="abc")

    def test_runconfig_cpu_limit_rejects_trailing_dot(self):
        with pytest.raises(ValueError):
            RunConfig(image="x", cpu_limit="1.")

    def test_timeout_defaults_to_none(self):
        config = RunConfig(image="alpine")
        assert config.timeout is None

    def test_timeout_accepts_positive_float(self):
        config = RunConfig(image="alpine", timeout=30.0)
        assert config.timeout == 30.0

    def test_timeout_zero_raises(self):
        with pytest.raises(ValueError, match="timeout must be positive"):
            RunConfig(image="alpine", timeout=0)

    def test_timeout_negative_raises(self):
        with pytest.raises(ValueError, match="timeout must be positive"):
            RunConfig(image="alpine", timeout=-1)


class TestImageInfo:
    def test_required_fields(self):
        info = ImageInfo(id="sha256:abc123")
        assert info.id == "sha256:abc123"

    def test_defaults(self):
        info = ImageInfo(id="sha256:abc123")
        assert info.tags == ()
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
        assert info.tags == ("alpine:latest",)
        assert info.size == 5000000
        assert info.created == "2024-01-01T00:00:00Z"
        assert info.labels == {"maintainer": "test"}


class TestContainerInfo:
    def test_state_is_typed_as_container_state(self):
        fs = {f.name: f for f in fields(ContainerInfo)}
        assert fs["state"].type is ContainerState

    def test_required_fields(self):
        info = ContainerInfo(
            id="abc123",
            name="my-container",
            image="alpine",
            state="running",
            status="Up 2h",
        )
        assert info.id == "abc123"
        assert info.name == "my-container"
        assert info.image == "alpine"
        assert info.state == "running"
        assert info.status == "Up 2h"

    def test_defaults(self):
        info = ContainerInfo(
            id="abc", name="c1", image="alpine", state="running", status="Up 2h"
        )
        assert info.created is None
        assert info.ports == ()
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
            ports=[PortMapping(container_port=80, host_ip=None)],
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
        info = VolumeInfo(
            name="my-vol",
            driver="local",
            mountpoint="/mnt/data",
            labels={"app": "test"},
        )
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
        info = NetworkInfo(
            id="net1", name="host", driver="host", scope="local", labels={"app": "test"}
        )
        assert info.id == "net1"
        assert info.name == "host"
        assert info.driver == "host"
        assert info.scope == "local"
        assert info.labels == {"app": "test"}


class TestFrozenValueObjects:
    """All value-object dataclasses must be frozen (E1).

    Reassigning any field after construction must raise FrozenInstanceError.
    This is the regression guard for the freeze — if someone removes
    frozen=True from a value object, the corresponding parametrize case
    fails.
    """

    @pytest.mark.parametrize(
        "cls,kwargs,field_to_mutate,new_value",
        [
            (VolumeMount, {"source": "/s", "target": "/t"}, "source", "/x"),
            (
                PortMapping,
                {"container_port": 80, "host_ip": None},
                "container_port",
                81,
            ),
            (
                BuildContext,
                {"build_file_content": "FROM alpine"},
                "build_file_content",
                "x",
            ),
            (RunConfig, {"image": "alpine"}, "image", "other"),
            (ImageInfo, {"id": "sha256:abc"}, "id", "sha256:zzz"),
            (
                ContainerInfo,
                {
                    "id": "c",
                    "name": "n",
                    "image": "i",
                    "state": ContainerState.RUNNING,
                    "status": "up",
                },
                "id",
                "zzz",
            ),
            (VolumeInfo, {"name": "v", "driver": "local"}, "name", "v2"),
            (
                ExecResult,
                {"returncode": 0, "stdout": "", "stderr": ""},
                "returncode",
                1,
            ),
            (
                RawExecResult,
                {"returncode": 0, "stdout": b"", "stderr": b""},
                "returncode",
                1,
            ),
            (
                NetworkInfo,
                {"id": "n", "name": "n", "driver": "d", "scope": "s"},
                "id",
                "n2",
            ),
        ],
        ids=[
            "VolumeMount",
            "PortMapping",
            "BuildContext",
            "RunConfig",
            "ImageInfo",
            "ContainerInfo",
            "VolumeInfo",
            "ExecResult",
            "RawExecResult",
            "NetworkInfo",
        ],
    )
    def test_frozen_blocks_reassignment(self, cls, kwargs, field_to_mutate, new_value):
        obj = cls(**kwargs)
        with pytest.raises(FrozenInstanceError):
            setattr(obj, field_to_mutate, new_value)


class TestDeepImmutability:
    def test_build_context_mapping_fields_are_mappingproxy(self):
        ctx = BuildContext(
            build_file_content="FROM alpine",
            files={"a": b"1"},
            build_args={"K": "V"},
            labels={"app": "test"},
            build_contexts={"root": "/repo"},
        )
        assert isinstance(ctx.files, MappingProxyType)
        assert isinstance(ctx.build_args, MappingProxyType)
        assert isinstance(ctx.labels, MappingProxyType)
        assert isinstance(ctx.build_contexts, MappingProxyType)

    def test_build_context_mapping_mutation_raises(self):
        ctx = BuildContext(build_file_content="FROM alpine", labels={"app": "test"})
        with pytest.raises(TypeError):
            ctx.labels["new"] = "x"

    def test_run_config_mapping_fields_are_mappingproxy(self):
        config = RunConfig(
            image="alpine", environment={"ENV": "prod"}, labels={"app": "test"}
        )
        assert isinstance(config.environment, MappingProxyType)
        assert isinstance(config.labels, MappingProxyType)

    def test_run_config_sequence_fields_are_tuples(self):
        config = RunConfig(
            image="alpine",
            volumes=[VolumeMount(source="/s", target="/t")],
            ports=[PortMapping(container_port=80, host_ip=None)],
            runtime_flags=["--cap-drop=ALL"],
            command=["echo", "hi"],
        )
        assert isinstance(config.volumes, tuple)
        assert isinstance(config.ports, tuple)
        assert isinstance(config.runtime_flags, tuple)
        assert isinstance(config.command, tuple)

    def test_run_config_sequence_field_mutation_raises(self):
        config = RunConfig(image="alpine", runtime_flags=["--cap-drop=ALL"])
        with pytest.raises(AttributeError):
            config.runtime_flags.append("--another")

    def test_image_info_fields_are_immutable_containers(self):
        info = ImageInfo(id="sha256:abc", tags=["latest"], labels={"k": "v"})
        assert isinstance(info.labels, MappingProxyType)
        assert isinstance(info.tags, tuple)
        with pytest.raises(TypeError):
            info.labels["new"] = "x"
        with pytest.raises(AttributeError):
            info.tags.append("new")

    def test_container_info_fields_are_immutable_containers(self):
        info = ContainerInfo(
            id="c1",
            name="n",
            image="i",
            state=ContainerState.RUNNING,
            status="up",
            ports=[PortMapping(container_port=80, host_ip=None)],
            labels={"app": "test"},
        )
        assert isinstance(info.labels, MappingProxyType)
        assert isinstance(info.ports, tuple)
        with pytest.raises(TypeError):
            info.labels["new"] = "x"
        with pytest.raises(AttributeError):
            info.ports.append(PortMapping(container_port=81, host_ip=None))

    def test_volume_info_labels_are_mappingproxy(self):
        info = VolumeInfo(name="v", driver="local", labels={"app": "test"})
        assert isinstance(info.labels, MappingProxyType)
        with pytest.raises(TypeError):
            info.labels["new"] = "x"

    def test_network_info_labels_are_mappingproxy(self):
        info = NetworkInfo(
            id="n", name="n", driver="d", scope="s", labels={"app": "test"}
        )
        assert isinstance(info.labels, MappingProxyType)
        with pytest.raises(TypeError):
            info.labels["new"] = "x"
