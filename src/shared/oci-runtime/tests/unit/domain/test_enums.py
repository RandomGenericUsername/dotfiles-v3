import pytest

from oci_runtime.domain.enums import (
    ContainerState,
    NetworkMode,
    RestartPolicy,
    RuntimeKind,
    VolumeMountType,
)


class TestRuntimeKind:
    @pytest.mark.parametrize(
        "member,expected",
        [
            ("DOCKER", "docker"),
            ("PODMAN", "podman"),
        ],
    )
    def test_members(self, member, expected):
        assert getattr(RuntimeKind, member).value == expected

    def test_runtime_kind_len(self):
        assert len(RuntimeKind) == 2

    @pytest.mark.parametrize(
        "member",
        ["DOCKER", "PODMAN"],
    )
    def test_runtime_kind_is_enum(self, member):
        assert isinstance(getattr(RuntimeKind, member), RuntimeKind)

    def test_runtime_kind_values_are_subcommand_compatible(self):
        for member in RuntimeKind:
            assert isinstance(member.value, str)
            assert member.value.isidentifier()


class TestContainerState:
    @pytest.mark.parametrize(
        "member,expected",
        [
            ("CREATED", "created"),
            ("RUNNING", "running"),
            ("PAUSED", "paused"),
            ("RESTARTING", "restarting"),
            ("REMOVING", "removing"),
            ("EXITED", "exited"),
            ("DEAD", "dead"),
            ("UNKNOWN", "unknown"),
        ],
    )
    def test_members(self, member, expected):
        assert getattr(ContainerState, member).value == expected

    @pytest.mark.parametrize("raw", ["deleting", ""])
    def test_missing_fallback(self, raw):
        assert ContainerState(raw) is ContainerState.UNKNOWN

    def test_container_state_count(self):
        assert len(ContainerState) == 8

    def test_container_state_all_values_strings(self):
        for member in ContainerState:
            assert isinstance(member.value, str)

    @pytest.mark.parametrize(
        "member,expected",
        [
            ("CREATED", "created"),
            ("RUNNING", "running"),
            ("PAUSED", "paused"),
            ("RESTARTING", "restarting"),
            ("REMOVING", "removing"),
            ("EXITED", "exited"),
            ("DEAD", "dead"),
            ("UNKNOWN", "unknown"),
        ],
    )
    def test_container_state_enum_values(self, member, expected):
        assert ContainerState[member].value == expected


class TestRestartPolicy:
    @pytest.mark.parametrize(
        "member,expected",
        [
            ("NO", "no"),
            ("ON_FAILURE", "on-failure"),
            ("ALWAYS", "always"),
            ("UNLESS_STOPPED", "unless-stopped"),
        ],
    )
    def test_members(self, member, expected):
        assert getattr(RestartPolicy, member).value == expected


class TestNetworkMode:
    @pytest.mark.parametrize(
        "member,expected",
        [
            ("BRIDGE", "bridge"),
            ("HOST", "host"),
            ("NONE", "none"),
            ("CONTAINER", "container"),
        ],
    )
    def test_members(self, member, expected):
        assert getattr(NetworkMode, member).value == expected


class TestSubcommandValues:
    @pytest.mark.parametrize(
        "kind,expected_subcommand",
        [
            (RuntimeKind.DOCKER, "docker"),
            (RuntimeKind.PODMAN, "podman"),
        ],
    )
    def test_subcommand_matches_runtime_kind(self, kind, expected_subcommand):
        assert kind.value == expected_subcommand

    def test_all_runtime_kinds_have_subcommand(self):
        for kind in RuntimeKind:
            assert isinstance(kind.value, str)
            assert len(kind.value) > 0


class TestVolumeMountType:
    @pytest.mark.parametrize(
        "member,expected",
        [
            ("BIND", "bind"),
            ("VOLUME", "volume"),
            ("TMPFS", "tmpfs"),
        ],
    )
    def test_members(self, member, expected):
        assert getattr(VolumeMountType, member).value == expected


class TestSubcommand:
    @pytest.mark.parametrize(
        "member,expected",
        [
            ("RUN", "run"),
            ("BUILD", "build"),
            ("TAG", "tag"),
            ("PUSH", "push"),
            ("PULL", "pull"),
            ("RMI", "rmi"),
            ("RM", "rm"),
            ("EXEC", "exec"),
            ("LOGS", "logs"),
            ("INSPECT", "inspect"),
            ("STOP", "stop"),
            ("START", "start"),
            ("RESTART", "restart"),
            ("PRUNE", "prune"),
            ("CREATE", "create"),
            ("CONNECT", "connect"),
            ("DISCONNECT", "disconnect"),
            ("LIST", "list"),
            ("IMAGE", "image"),
            ("CONTAINER", "container"),
            ("VOLUME", "volume"),
            ("NETWORK", "network"),
        ],
    )
    def test_subcommand_values(self, member, expected):
        from oci_runtime.domain.enums import Subcommand

        assert getattr(Subcommand, member).value == expected


def test_subcommand_not_exported():
    import oci_runtime

    assert "Subcommand" not in oci_runtime.__all__
