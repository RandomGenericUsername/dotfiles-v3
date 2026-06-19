import pytest

from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.adapters.managers.image import CliImageManager
from oci_runtime.adapters.managers.network import CliNetworkManager
from oci_runtime.adapters.managers.volume import CliVolumeManager
from oci_runtime.domain.types import BuildContext, ImageInfo, RunConfig
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.domain.types import ExecResult
from tests.helpers.mock_parsers import (
    MockContainerParser,
    MockImageParser,
    MockNetworkParser,
    MockVolumeParser,
)
from tests.helpers.mock_transport import RecordingTransport, RecordingStreamingTransport, FakeTtyDetector


@pytest.fixture
def caps():
    return RuntimeCapabilities(
        supports_log_drivers=True,
        tar_entry_name="Dockerfile",
        default_build_flags=["--quiet"],
    )


@pytest.fixture
def t():
    return RecordingTransport("docker")


@pytest.fixture
def st():
    return RecordingStreamingTransport("docker")


# ─── Helpers ───

INSPECT_CONTAINER_JSON = b'[{"Id":"abc123","Name":"/c1","Config":{"Image":"alpine"},"State":{"Status":"running","ExitCode":0,"Running":true},"Created":"2024-01-01T00:00:00Z","HostConfig":{},"NetworkSettings":{"Ports":{}}}]'
LIST_CONTAINER_JSON = b'[{"Id":"abc123","Names":["/c1"],"Image":"alpine","ImageID":"sha256:x","State":"running","Status":"Up 2h","Created":1704067200,"Ports":[],"Labels":{}}]'
INSPECT_IMAGE_JSON = b'[{"Id":"sha256:img123","RepoTags":["alpine:latest"],"Size":5000000,"Created":"2024-01-01T00:00:00Z","Labels":{}}]'
LIST_IMAGE_JSON = b'[{"Id":"sha256:img123","RepoTags":["alpine:latest"],"Size":5000000,"Created":1704067200,"Labels":{}}]'
INSPECT_VOLUME_JSON = b'[{"Name":"myvol","Driver":"local","Mountpoint":"/data","Labels":{}}]'
LIST_VOLUME_JSON = b'[{"Name":"myvol","Driver":"local","Mountpoint":"/data","Labels":{}}]'
INSPECT_NETWORK_JSON = b'[{"Id":"net123","Name":"bridge","Driver":"bridge","Scope":"local","Labels":{}}]'
LIST_NETWORK_JSON = b'[{"Id":"net123","Name":"bridge","Driver":"bridge","Scope":"local","Labels":{}}]'


class TestImageManagerCommands:
    def test_build_tar_command(self, t, caps):
        t._responses = {"docker build -t myimg - --quiet": ExecResult(0, b"abc123\n", b"")}
        mgr = CliImageManager(t, MockImageParser(), caps)
        ctx = BuildContext(build_file_content="FROM alpine")
        result = mgr.build(ctx, "myimg", timeout=30)
        assert t.calls[0].command == ["docker", "build", "-t", "myimg", "-", "--quiet"]
        assert isinstance(result, str)

    def test_tag_command(self, t, caps):
        t._responses = {"docker tag alpine test:latest": ExecResult(0, b"", b"")}
        mgr = CliImageManager(t, MockImageParser(), caps)
        mgr.tag("alpine", "test:latest")
        assert t.calls[0].command == ["docker", "tag", "alpine", "test:latest"]

    def test_push_command(self, t, caps):
        t._responses = {"docker push alpine": ExecResult(0, b"", b"")}
        mgr = CliImageManager(t, MockImageParser(), caps)
        mgr.push("alpine", timeout=60)
        assert t.calls[0].command == ["docker", "push", "alpine"]

    def test_pull_command_and_parsed_id(self, t, caps):
        t._responses = {"docker pull alpine": ExecResult(0, b"Status: Downloaded alpine:latest\n", b"")}
        mgr = CliImageManager(t, MockImageParser(), caps)
        result = mgr.pull("alpine", timeout=60)
        assert t.calls[0].command == ["docker", "pull", "alpine"]
        assert isinstance(result, str)

    def test_remove_command(self, t, caps):
        t._responses = {"docker rmi alpine": ExecResult(0, b"", b"")}
        mgr = CliImageManager(t, MockImageParser(), caps)
        mgr.remove("alpine")
        assert t.calls[0].command == ["docker", "rmi", "alpine"]

    def test_remove_force(self, t, caps):
        t._responses = {"docker rmi alpine --force": ExecResult(0, b"", b"")}
        mgr = CliImageManager(t, MockImageParser(), caps)
        mgr.remove("alpine", force=True)
        assert t.calls[0].command == ["docker", "rmi", "alpine", "--force"]

    def test_inspect_command_and_parsed_info(self, t, caps):
        t._responses = {"docker image inspect --format json alpine": ExecResult(0, INSPECT_IMAGE_JSON, b"")}
        mgr = CliImageManager(t, MockImageParser(), caps)
        info = mgr.inspect("alpine")
        assert t.calls[0].command == ["docker", "image", "inspect", "--format", "json", "alpine"]
        assert isinstance(info.id, str) and info.id.startswith("sha256:")

    def test_list_command_and_parsed(self, t, caps):
        t._responses = {"docker image list": ExecResult(0, LIST_IMAGE_JSON, b"")}
        mgr = CliImageManager(t, MockImageParser(), caps)
        result = mgr.list()
        assert t.calls[0].command == ["docker", "image", "list"]
        assert len(result) == 1
        assert isinstance(result[0], ImageInfo)

    def test_list_with_filter(self, t, caps):
        t._responses = {"docker image list --filter label=app=web": ExecResult(0, b"[]", b"")}
        mgr = CliImageManager(t, MockImageParser(), caps)
        mgr.list(filters={"label": "app=web"})
        assert t.calls[0].command == ["docker", "image", "list", "--filter", "label=app=web"]

    def test_prune_command(self, t, caps):
        t._responses = {"docker image prune --force": ExecResult(0, b"", b"")}
        mgr = CliImageManager(t, MockImageParser(), caps)
        result = mgr.prune()
        assert t.calls[0].command == ["docker", "image", "prune", "--force"]
        assert result == {"deleted": 0, "reclaimed_bytes": 0}

    def test_prune_all(self, t, caps):
        t._responses = {"docker image prune --force --all": ExecResult(0, b"", b"")}
        mgr = CliImageManager(t, MockImageParser(), caps)
        mgr.prune(show_all=True)
        assert t.calls[0].command == ["docker", "image", "prune", "--force", "--all"]

    def test_exists_true_delegates_to_inspect(self, t, caps):
        t._responses = {"docker image inspect --format json alpine": ExecResult(0, INSPECT_IMAGE_JSON, b"")}
        mgr = CliImageManager(t, MockImageParser(), caps)
        assert mgr.exists("alpine") is True

    def test_exists_false_delegates_to_inspect(self, t, caps):
        t._responses = {"docker image inspect --format json nonexistent": ExecResult(1, b"", b"No such image: nonexistent")}
        mgr = CliImageManager(t, MockImageParser(), caps)
        assert mgr.exists("nonexistent") is False


class TestContainerManagerCommands:
    def test_run_minimal(self, t, st, caps):
        st._responses = {"docker run -d alpine": ExecResult(0, b"abc123\n", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        result = mgr.run(RunConfig(image="alpine"))
        assert st.calls[0].command == ["docker", "run", "-d", "alpine"]
        assert result == "abc123"

    def test_run_with_name(self, t, st, caps):
        st._responses = {"docker run -d --name myapp alpine": ExecResult(0, b"abc123", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        mgr.run(RunConfig(image="alpine", name="myapp"))
        assert st.calls[0].command == ["docker", "run", "-d", "--name", "myapp", "alpine"]

    def test_run_with_all_options(self, t, st, caps):
        st._responses = {"docker run -d --rm --name myapp -t -i -u root -w /app --hostname myhost --entrypoint /bin/sh --network host --restart always --log-driver json-file --privileged --read-only -m 512m --cpus 2 -e FOO=bar -v /host:/container -p 8080:80/tcp -l app=web alpine echo hi": ExecResult(0, b"abc123", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        from oci_runtime.domain.enums import NetworkMode, RestartPolicy
        from oci_runtime.domain.types import PortMapping, VolumeMount
        config = RunConfig(
            image="alpine",
            name="myapp",
            command=["echo", "hi"],
            entrypoint="/bin/sh",
            environment={"FOO": "bar"},
            volumes=[VolumeMount(source="/host", target="/container", type="bind")],
            ports=[PortMapping(container_port=80, host_port=8080)],
            network=NetworkMode.HOST,
            restart_policy=RestartPolicy.ALWAYS,
            detach=True,
            remove=True,
            tty=False,
            stdin_open=True,
            user="root",
            working_dir="/app",
            hostname="myhost",
            log_driver="json-file",
            privileged=True,
            read_only=True,
            memory_limit="512m",
            cpu_limit="2",
            labels={"app": "web"},
        )
        mgr.run(config)
        assert st.calls[0].command == ["docker", "run", "-d", "--rm", "--name", "myapp", "-i", "-u", "root", "-w", "/app", "--hostname", "myhost", "--entrypoint", "/bin/sh", "--network", "host", "--restart", "always", "--log-driver", "json-file", "--privileged", "--read-only", "-m", "512m", "--cpus", "2", "-e", "FOO=bar", "-v", "/host:/container", "-p", "8080:80/tcp", "-l", "app=web", "alpine", "echo", "hi"]

    def test_run_detach_false(self, t, st, caps):
        st._responses = {"docker run alpine": ExecResult(0, b"abc123", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        mgr.run(RunConfig(image="alpine", detach=False))
        assert st.calls[0].command == ["docker", "run", "alpine"]

    def test_run_stream(self, t, st, caps):
        st._responses = {"docker run -d alpine": ExecResult(0, b"", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        result = mgr.run(RunConfig(image="alpine", stream_output=True))
        assert result == ""

    def test_run_podman_flags(self):
        pcaps = RuntimeCapabilities(
            needs_userns_keep_id=True,
            tar_entry_name="Containerfile",
            default_run_flags=["--userns=keep-id"],
        )
        podman_t = RecordingTransport("podman", {"podman run --userns=keep-id -d alpine": ExecResult(0, b"abc123", b"")})
        podman_st = RecordingStreamingTransport("podman", {"podman run --userns=keep-id -d alpine": ExecResult(0, b"abc123", b"")})
        mgr = CliContainerManager(podman_t, MockContainerParser(), pcaps, streaming=podman_st, tty_detector=FakeTtyDetector())
        mgr.run(RunConfig(image="alpine"))
        assert podman_st.calls[0].command == ["podman", "run", "--userns=keep-id", "-d", "alpine"]

    def test_start(self, t, st, caps):
        t._responses = {"docker start ctr1": ExecResult(0, b"", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        mgr.start("ctr1")
        assert t.calls[0].command == ["docker", "start", "ctr1"]

    def test_stop(self, t, st, caps):
        t._responses = {"docker stop -t 10 ctr1": ExecResult(0, b"", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        mgr.stop("ctr1")
        assert t.calls[0].command == ["docker", "stop", "-t", "10", "ctr1"]

    def test_restart(self, t, st, caps):
        t._responses = {"docker restart -t 10 ctr1": ExecResult(0, b"", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        mgr.restart("ctr1")
        assert t.calls[0].command == ["docker", "restart", "-t", "10", "ctr1"]

    def test_remove(self, t, st, caps):
        t._responses = {"docker rm ctr1": ExecResult(0, b"", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        mgr.remove("ctr1")
        assert t.calls[0].command == ["docker", "rm", "ctr1"]

    def test_remove_force_volumes(self, t, st, caps):
        t._responses = {"docker rm ctr1 -f -v": ExecResult(0, b"", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        mgr.remove("ctr1", force=True, volumes=True)
        assert t.calls[0].command == ["docker", "rm", "ctr1", "-f", "-v"]

    def test_inspect_command_and_parsed(self, t, st, caps):
        t._responses = {"docker container inspect --format json ctr1": ExecResult(0, INSPECT_CONTAINER_JSON, b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        info = mgr.inspect("ctr1")
        assert t.calls[0].command == ["docker", "container", "inspect", "--format", "json", "ctr1"]
        assert info.id == "abc"

    def test_list(self, t, st, caps):
        t._responses = {"docker container list": ExecResult(0, LIST_CONTAINER_JSON, b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        result = mgr.list()
        assert t.calls[0].command == ["docker", "container", "list"]
        assert len(result) == 1

    def test_list_all(self, t, st, caps):
        t._responses = {"docker container list -a": ExecResult(0, b"[]", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        mgr.list(show_all=True)
        assert t.calls[0].command == ["docker", "container", "list", "-a"]

    def test_list_with_filter(self, t, st, caps):
        t._responses = {"docker container list --filter name=web": ExecResult(0, b"[]", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        mgr.list(filters={"name": "web"})
        assert t.calls[0].command == ["docker", "container", "list", "--filter", "name=web"]

    def test_logs(self, t, st, caps):
        t._responses = {"docker logs ctr1": ExecResult(0, b"log output\n", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        result = "".join(mgr.logs("ctr1"))
        assert t.calls[0].command == ["docker", "logs", "ctr1"]
        assert result == "log output\n"

    def test_logs_follow_tail(self, t, st, caps):
        st._stream_responses = {"docker logs ctr1 --follow --tail 50": [b"", b""]}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        list(mgr.logs("ctr1", follow=True, tail=50))
        assert st.calls[0].command == ["docker", "logs", "ctr1", "--follow", "--tail", "50"]

    def test_logs_follow_streams_chunks(self, t, st, caps):
        st._stream_responses["docker logs ctr1 --follow"] = [b"chunk1\n", b"chunk2\n"]
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        chunks = list(mgr.logs("ctr1", follow=True))
        assert chunks == ["chunk1\n", "chunk2\n"]

    def test_exec(self, t, st, caps):
        t._responses = {"docker exec ctr1 ls -la": ExecResult(0, b"file1\nfile2\n", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        result = mgr.exec_container("ctr1", ["ls", "-la"])
        assert t.calls[0].command == ["docker", "exec", "ctr1", "ls", "-la"]
        assert result.returncode == 0
        assert result.stdout == "file1\nfile2\n"

    def test_exec_detach_user(self, t, st, caps):
        t._responses = {"docker exec -d -u root ctr1 ls": ExecResult(0, b"", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        mgr.exec_container("ctr1", ["ls"], detach=True, user="root")
        assert t.calls[0].command == ["docker", "exec", "-d", "-u", "root", "ctr1", "ls"]

    def test_prune(self, t, st, caps):
        t._responses = {"docker container prune --force": ExecResult(0, b"", b"")}
        mgr = CliContainerManager(t, MockContainerParser(), caps, streaming=st, tty_detector=FakeTtyDetector())
        result = mgr.prune()
        assert t.calls[0].command == ["docker", "container", "prune", "--force"]
        assert result == {"deleted": 0, "reclaimed_bytes": 0}


class TestVolumeManagerCommands:
    def test_create(self, t, caps):
        t._responses = {"docker volume create --driver local myvol": ExecResult(0, b"myvol\n", b"")}
        mgr = CliVolumeManager(t, MockVolumeParser(), caps)
        result = mgr.create("myvol")
        assert t.calls[0].command == ["docker", "volume", "create", "--driver", "local", "myvol"]
        assert result == "myvol"

    def test_create_with_labels(self, t, caps):
        t._responses = {"docker volume create --driver local myvol --label app=web": ExecResult(0, b"myvol", b"")}
        mgr = CliVolumeManager(t, MockVolumeParser(), caps)
        mgr.create("myvol", labels={"app": "web"})
        assert t.calls[0].command == ["docker", "volume", "create", "--driver", "local", "myvol", "--label", "app=web"]

    def test_remove(self, t, caps):
        t._responses = {"docker volume rm myvol": ExecResult(0, b"", b"")}
        mgr = CliVolumeManager(t, MockVolumeParser(), caps)
        mgr.remove("myvol")
        assert t.calls[0].command == ["docker", "volume", "rm", "myvol"]

    def test_remove_force(self, t, caps):
        t._responses = {"docker volume rm myvol -f": ExecResult(0, b"", b"")}
        mgr = CliVolumeManager(t, MockVolumeParser(), caps)
        mgr.remove("myvol", force=True)
        assert t.calls[0].command == ["docker", "volume", "rm", "myvol", "-f"]

    def test_inspect(self, t, caps):
        t._responses = {"docker volume inspect --format json myvol": ExecResult(0, INSPECT_VOLUME_JSON, b"")}
        mgr = CliVolumeManager(t, MockVolumeParser(), caps)
        info = mgr.inspect("myvol")
        assert t.calls[0].command == ["docker", "volume", "inspect", "--format", "json", "myvol"]
        assert info.name == "my-vol"

    def test_list(self, t, caps):
        t._responses = {"docker volume list": ExecResult(0, LIST_VOLUME_JSON, b"")}
        mgr = CliVolumeManager(t, MockVolumeParser(), caps)
        result = mgr.list()
        assert t.calls[0].command == ["docker", "volume", "list"]
        assert len(result) == 1

    def test_list_with_filter(self, t, caps):
        t._responses = {"docker volume list --filter label=app=web": ExecResult(0, b"[]", b"")}
        mgr = CliVolumeManager(t, MockVolumeParser(), caps)
        mgr.list(filters={"label": "app=web"})
        assert t.calls[0].command == ["docker", "volume", "list", "--filter", "label=app=web"]

    def test_prune(self, t, caps):
        t._responses = {"docker volume prune --force": ExecResult(0, b"", b"")}
        mgr = CliVolumeManager(t, MockVolumeParser(), caps)
        result = mgr.prune()
        assert t.calls[0].command == ["docker", "volume", "prune", "--force"]
        assert result == {"deleted": 0, "reclaimed_bytes": 0}


class TestNetworkManagerCommands:
    def test_create(self, t, caps):
        t._responses = {"docker network create --driver bridge mynet": ExecResult(0, b"mynet\n", b"")}
        mgr = CliNetworkManager(t, MockNetworkParser(), caps)
        result = mgr.create("mynet")
        assert t.calls[0].command == ["docker", "network", "create", "--driver", "bridge", "mynet"]
        assert result == "mynet"

    def test_create_with_labels(self, t, caps):
        t._responses = {"docker network create --driver bridge mynet --label app=web": ExecResult(0, b"mynet", b"")}
        mgr = CliNetworkManager(t, MockNetworkParser(), caps)
        mgr.create("mynet", labels={"app": "web"})
        assert t.calls[0].command == ["docker", "network", "create", "--driver", "bridge", "mynet", "--label", "app=web"]

    def test_create_macvlan(self, t, caps):
        t._responses = {"docker network create --driver macvlan mynet": ExecResult(0, b"mynet", b"")}
        mgr = CliNetworkManager(t, MockNetworkParser(), caps)
        mgr.create("mynet", driver="macvlan")
        assert t.calls[0].command == ["docker", "network", "create", "--driver", "macvlan", "mynet"]

    def test_remove(self, t, caps):
        t._responses = {"docker network rm mynet": ExecResult(0, b"", b"")}
        mgr = CliNetworkManager(t, MockNetworkParser(), caps)
        mgr.remove("mynet")
        assert t.calls[0].command == ["docker", "network", "rm", "mynet"]

    def test_connect(self, t, caps):
        t._responses = {"docker network connect mynet ctr1": ExecResult(0, b"", b"")}
        mgr = CliNetworkManager(t, MockNetworkParser(), caps)
        mgr.connect("mynet", "ctr1")
        assert t.calls[0].command == ["docker", "network", "connect", "mynet", "ctr1"]

    def test_disconnect(self, t, caps):
        t._responses = {"docker network disconnect mynet ctr1": ExecResult(0, b"", b"")}
        mgr = CliNetworkManager(t, MockNetworkParser(), caps)
        mgr.disconnect("mynet", "ctr1")
        assert t.calls[0].command == ["docker", "network", "disconnect", "mynet", "ctr1"]

    def test_disconnect_force(self, t, caps):
        t._responses = {"docker network disconnect mynet ctr1 -f": ExecResult(0, b"", b"")}
        mgr = CliNetworkManager(t, MockNetworkParser(), caps)
        mgr.disconnect("mynet", "ctr1", force=True)
        assert t.calls[0].command == ["docker", "network", "disconnect", "mynet", "ctr1", "-f"]

    def test_inspect(self, t, caps):
        t._responses = {"docker network inspect --format json mynet": ExecResult(0, INSPECT_NETWORK_JSON, b"")}
        mgr = CliNetworkManager(t, MockNetworkParser(), caps)
        info = mgr.inspect("mynet")
        assert t.calls[0].command == ["docker", "network", "inspect", "--format", "json", "mynet"]
        assert info.id == "n1"

    def test_list(self, t, caps):
        t._responses = {"docker network list": ExecResult(0, LIST_NETWORK_JSON, b"")}
        mgr = CliNetworkManager(t, MockNetworkParser(), caps)
        result = mgr.list()
        assert t.calls[0].command == ["docker", "network", "list"]
        assert len(result) == 1

    def test_prune(self, t, caps):
        t._responses = {"docker network prune --force": ExecResult(0, b"", b"")}
        mgr = CliNetworkManager(t, MockNetworkParser(), caps)
        result = mgr.prune()
        assert t.calls[0].command == ["docker", "network", "prune", "--force"]
        assert result == {"deleted": 0, "reclaimed_bytes": 0}
