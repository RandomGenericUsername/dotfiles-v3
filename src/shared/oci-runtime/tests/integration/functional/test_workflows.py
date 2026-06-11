import pytest
from pathlib import Path

from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ImageNotFoundError,
    NetworkNotFoundError,
    VolumeNotFoundError,
)
from oci_runtime.domain.types import (
    BuildContext,
    ContainerInfo,
    NetworkInfo,
    PortMapping,
    RunConfig,
    VolumeInfo,
    VolumeMount,
)
from oci_runtime.domain.enums import NetworkMode, RestartPolicy
from oci_runtime.ports.transport import ExecResult
from tests.helpers.mock_transport import RecordingTransport


def _inject_responses(transport, responses: dict[str, ExecResult]):
    transport._responses.update(responses)


class TestImageLifecycle:
    def test_image_lifecycle(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker pull alpine": ExecResult(0, b"Status: Downloaded newer image for alpine:latest\n", b""),
            "docker image list": ExecResult(0, b'[{"Id":"sha256:abc","RepoTags":["alpine:latest"],"Size":5000000,"Created":1704067200,"Labels":{}}]', b""),
            "docker image inspect --format json alpine": ExecResult(0, b'[{"Id":"sha256:abc","RepoTags":["alpine:latest"],"Size":5000000,"Created":"2024-01-01T00:00:00Z","Labels":{}}]', b""),
            "docker tag alpine myalpine:v1": ExecResult(0, b"", b""),
            "docker rmi myalpine:v1": ExecResult(0, b"", b""),
        })
        img = docker_engine.images
        img.pull("alpine")
        images = img.list()
        assert len(images) == 1
        img.tag("alpine", "myalpine:v1")
        img.remove("myalpine:v1")
        _inject_responses(t, {
            "docker image inspect --format json myalpine:v1": ExecResult(1, b"", b"Error: No such image: myalpine:v1"),
        })
        with pytest.raises(ImageNotFoundError):
            img.inspect("myalpine:v1")

    def test_image_exists_true(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker pull alpine": ExecResult(0, b"abc\n", b""),
            "docker image inspect --format json alpine": ExecResult(0, b'[{"Id":"sha256:abc","RepoTags":["alpine:latest"]}]', b""),
        })
        docker_engine.images.pull("alpine")
        assert docker_engine.images.exists("alpine") is True

    def test_image_exists_false(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker image inspect --format json nonexistent": ExecResult(1, b"", b"Error: No such image"),
        })
        assert docker_engine.images.exists("nonexistent") is False

    def test_build_from_dockerfile_tar(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker build -t myimg - --quiet": ExecResult(0, b"buildabc123\n", b""),
        })
        ctx = BuildContext(build_file_content="FROM alpine\nRUN echo hi")
        docker_engine.images.build(ctx, "myimg")
        assert "-" in t.calls[0].command
        assert t.calls[0].kwargs["input_data"] is not None

    def test_build_from_dockerfile_path(self, docker_engine: CliRuntime, tmp_path: Path):
        t = docker_engine._transport
        dfile = tmp_path / "Dockerfile"
        dfile.write_text("FROM alpine")
        _inject_responses(t, {
            f"docker build -t myimg -f {dfile} {tmp_path} --quiet": ExecResult(0, b"def456\n", b""),
        })
        ctx = BuildContext(build_file_path=dfile)
        docker_engine.images.build(ctx, "myimg")
        assert "-f" in t.calls[0].command

    def test_pull_nonexistent_image(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker pull nonexistent:latest": ExecResult(1, b"", b"pull access denied for nonexistent:latest"),
        })
        with pytest.raises(ImageNotFoundError):
            docker_engine.images.pull("nonexistent:latest")


class TestContainerLifecycle:
    def test_container_lifecycle(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker run -d alpine": ExecResult(0, b"ctr1\n", b""),
            "docker container list --format json": ExecResult(0, b'[{"Id":"ctr1","Names":["/ctr1"],"Image":"alpine","State":"running","Created":1704067200,"Ports":[],"Labels":{}}]', b""),
            "docker container inspect --format json ctr1": ExecResult(0, b'[{"Id":"ctr1","Name":"/ctr1","Config":{"Image":"alpine"},"State":{"Status":"running","ExitCode":0,"Running":true},"Created":"2024-01-01T00:00:00Z","HostConfig":{},"NetworkSettings":{"Ports":{}}}]', b""),
            "docker stop -t 10 ctr1": ExecResult(0, b"ctr1\n", b""),
            "docker start ctr1": ExecResult(0, b"ctr1\n", b""),
            "docker logs ctr1": ExecResult(0, b"hello from container\n", b""),
            "docker exec ctr1 echo ok": ExecResult(0, b"ok\n", b""),
            "docker rm ctr1": ExecResult(0, b"ctr1\n", b""),
        })
        mgr = docker_engine.containers
        cid = mgr.run(RunConfig(image="alpine"))
        assert cid == "ctr1"
        containers = mgr.list()
        assert len(containers) == 1
        info = mgr.inspect("ctr1")
        assert info.id == "abc"
        mgr.stop("ctr1")
        mgr.start("ctr1")
        logs = "".join(mgr.logs("ctr1"))
        assert logs == "hello from container\n"
        result = mgr.exec_container("ctr1", ["echo", "ok"])
        assert result.returncode == 0
        assert result.stdout == "ok\n"
        mgr.remove("ctr1")
        _inject_responses(t, {
            "docker container inspect --format json ctr1": ExecResult(1, b"", b"Error: No such container"),
        })
        with pytest.raises(ContainerNotFoundError):
            mgr.inspect("ctr1")

    def test_container_run_with_all_options(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker run -d --rm --name myapp -i -u root -w /app --hostname myhost --entrypoint /bin/sh --network host --restart always --log-driver json-file --privileged --read-only -m 512m --cpus 2 -e FOO=bar -v /host:/container -p 8080:80/tcp -l app=web alpine echo hi": ExecResult(0, b"ctr1\n", b""),
        })
        cid = docker_engine.containers.run(RunConfig(
            image="alpine", name="myapp", command=["echo", "hi"], entrypoint=["/bin/sh"],
            environment={"FOO": "bar"}, volumes=[VolumeMount(source="/host", target="/container", type="bind")],
            ports=[PortMapping(container_port=80, host_port=8080)],
            network=NetworkMode.HOST, restart_policy=RestartPolicy.ALWAYS,
            detach=True, remove=True, tty=False, stdin_open=True, user="root",
            working_dir="/app", hostname="myhost", log_driver="json-file",
            privileged=True, read_only=True, memory_limit="512m", cpu_limit="2",
            labels={"app": "web"},
        ))
        assert cid == "ctr1"

    def test_container_logs_with_options(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker run -d alpine": ExecResult(0, b"ctr1", b""),
        })
        t._stream_responses["docker logs ctr1 --follow --tail 50"] = [b"log output\n"]
        docker_engine.containers.run(RunConfig(image="alpine"))
        logs = "".join(docker_engine.containers.logs("ctr1", follow=True, tail=50))
        assert logs == "log output\n"

    def test_container_exec_with_options(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker run -d alpine": ExecResult(0, b"ctr1", b""),
            "docker exec -d -u root ctr1 ls": ExecResult(0, b"", b""),
        })
        docker_engine.containers.run(RunConfig(image="alpine"))
        docker_engine.containers.exec_container("ctr1", ["ls"], detach=True, user="root")

    def test_container_exists_true(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker run -d alpine": ExecResult(0, b"ctr1", b""),
            "docker container inspect --format json ctr1": ExecResult(0, b'[{"Id":"ctr1","Name":"/ctr1","Config":{"Image":"alpine"},"State":{"Status":"running","ExitCode":0,"Running":true},"Created":"2024-01-01T00:00:00Z","HostConfig":{},"NetworkSettings":{"Ports":{}}}]', b""),
        })
        docker_engine.containers.run(RunConfig(image="alpine"))
        assert docker_engine.containers.exists("ctr1") is True

    def test_container_exists_false(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker container inspect --format json nonexistent": ExecResult(1, b"", b"Error: No such container"),
        })
        assert docker_engine.containers.exists("nonexistent") is False

    def test_inspect_nonexistent_container(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker container inspect --format json nonexistent": ExecResult(1, b"", b"Error: No such container"),
        })
        with pytest.raises(ContainerNotFoundError):
            docker_engine.containers.inspect("nonexistent")

    def test_container_prune_returns_real_data(self, docker_engine: CliRuntime):
        result = docker_engine.containers.prune()
        assert result == {"deleted": 0, "reclaimed_bytes": 0}


class TestVolumeLifecycle:
    def test_volume_lifecycle(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker volume create --driver local myvol": ExecResult(0, b"myvol\n", b""),
            "docker volume inspect --format json myvol": ExecResult(0, b'[{"Name":"myvol","Driver":"local","Mountpoint":"/data","Labels":{}}]', b""),
            "docker volume list": ExecResult(0, b'[{"Name":"myvol","Driver":"local","Mountpoint":"/data","Labels":{}}]', b""),
            "docker volume rm myvol": ExecResult(0, b"", b""),
        })
        mgr = docker_engine.volumes
        name = mgr.create("myvol")
        assert name == "myvol"
        info = mgr.inspect("myvol")
        assert info.name == "my-vol"
        volumes = mgr.list()
        assert len(volumes) == 1
        mgr.remove("myvol")
        _inject_responses(t, {
            "docker volume inspect --format json myvol": ExecResult(1, b"", b"Error: No such volume"),
        })
        with pytest.raises(VolumeNotFoundError):
            mgr.inspect("myvol")

    def test_volume_with_labels(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker volume create --driver local myvol --label app=web": ExecResult(0, b"myvol", b""),
            "docker volume inspect --format json myvol": ExecResult(0, b'[{"Name":"myvol","Driver":"local","Mountpoint":"/data","Labels":{"app":"web"}}]', b""),
            "docker volume rm myvol": ExecResult(0, b"", b""),
        })
        docker_engine.volumes.create("myvol", labels={"app": "web"})
        info = docker_engine.volumes.inspect("myvol")
        assert isinstance(info, VolumeInfo)
        docker_engine.volumes.remove("myvol")

    def test_remove_nonexistent_volume(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker volume rm nonexistent": ExecResult(1, b"", b"Error: No such volume"),
        })
        with pytest.raises(VolumeNotFoundError):
            docker_engine.volumes.remove("nonexistent")


class TestNetworkLifecycle:
    def test_network_lifecycle(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker network create --driver bridge mynet": ExecResult(0, b"mynet\n", b""),
            "docker network list": ExecResult(0, b'[{"Id":"net1","Name":"mynet","Driver":"bridge","Scope":"local","Labels":{}}]', b""),
            "docker network inspect --format json mynet": ExecResult(0, b'[{"Id":"net1","Name":"mynet","Driver":"bridge","Scope":"local","Labels":{}}]', b""),
            "docker network connect mynet ctr1": ExecResult(0, b"", b""),
            "docker network disconnect mynet ctr1": ExecResult(0, b"", b""),
            "docker network rm mynet": ExecResult(0, b"", b""),
        })
        mgr = docker_engine.networks
        name = mgr.create("mynet")
        assert name == "mynet"
        networks = mgr.list()
        assert len(networks) == 1
        info = mgr.inspect("mynet")
        assert info.name == "net1"
        mgr.connect("mynet", "ctr1")
        mgr.disconnect("mynet", "ctr1")
        mgr.remove("mynet")

    def test_network_with_labels_and_driver(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker network create --driver macvlan mynet --label env=prod": ExecResult(0, b"mynet", b""),
            "docker network inspect --format json mynet": ExecResult(0, b'[{"Id":"net1","Name":"mynet","Driver":"macvlan","Scope":"local","Labels":{"env":"prod"}}]', b""),
            "docker network rm mynet": ExecResult(0, b"", b""),
        })
        docker_engine.networks.create("mynet", driver="macvlan", labels={"env": "prod"})
        info = docker_engine.networks.inspect("mynet")
        assert isinstance(info, NetworkInfo)
        docker_engine.networks.remove("mynet")

    def test_disconnect_nonexistent_network(self, docker_engine: CliRuntime):
        t = docker_engine._transport
        _inject_responses(t, {
            "docker network disconnect net1 ctr1": ExecResult(1, b"", b"Error: No such network"),
        })
        with pytest.raises(NetworkNotFoundError):
            docker_engine.networks.disconnect("net1", "ctr1")
