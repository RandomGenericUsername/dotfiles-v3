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
