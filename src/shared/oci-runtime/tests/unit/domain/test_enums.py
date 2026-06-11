from enum import Enum, StrEnum

import pytest

from oci_runtime.domain.enums import (
    ContainerState,
    NetworkMode,
    RestartPolicy,
    RuntimeKind,
)


class TestRuntimeKind:
    def test_is_enum(self):
        assert issubclass(RuntimeKind, Enum)

    def test_has_docker(self):
        assert RuntimeKind.DOCKER.value == "docker"

    def test_has_podman(self):
        assert RuntimeKind.PODMAN.value == "podman"

    def test_closed_set_no_other(self):
        members = set(RuntimeKind.__members__)
        assert members == {"DOCKER", "PODMAN"}

    def test_no_other_fallback(self):
        assert not hasattr(RuntimeKind, "OTHER")


class TestContainerState:
    def test_is_strenum(self):
        assert issubclass(ContainerState, StrEnum)

    def test_has_created(self):
        assert ContainerState.CREATED == "created"

    def test_has_running(self):
        assert ContainerState.RUNNING == "running"

    def test_has_paused(self):
        assert ContainerState.PAUSED == "paused"

    def test_has_restarting(self):
        assert ContainerState.RESTARTING == "restarting"

    def test_has_removing(self):
        assert ContainerState.REMOVING == "removing"

    def test_has_exited(self):
        assert ContainerState.EXITED == "exited"

    def test_has_dead(self):
        assert ContainerState.DEAD == "dead"

    def test_closed_set_engine_states(self):
        members = set(ContainerState.__members__)
        assert members == {"CREATED", "RUNNING", "PAUSED", "RESTARTING", "REMOVING", "EXITED", "DEAD"}

    def test_unknown_state_raises_value_error(self):
        with pytest.raises(ValueError):
            ContainerState("unknown")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            ContainerState("")

    def test_strenum_is_str(self):
        assert isinstance(ContainerState.RUNNING, str)

    def test_strenum_equality_with_str(self):
        assert ContainerState.RUNNING == "running"

    def test_strenum_not_equal_to_wrong_str(self):
        assert ContainerState.RUNNING != "stopped"

    def test_strenum_fstring(self):
        assert f"{ContainerState.RUNNING}" == "running"


class TestRestartPolicy:
    def test_is_strenum(self):
        assert issubclass(RestartPolicy, StrEnum)

    def test_is_enum(self):
        assert issubclass(RestartPolicy, Enum)

    def test_has_no(self):
        assert RestartPolicy.NO.value == "no"

    def test_has_on_failure(self):
        assert RestartPolicy.ON_FAILURE.value == "on-failure"

    def test_has_always(self):
        assert RestartPolicy.ALWAYS.value == "always"

    def test_has_unless_stopped(self):
        assert RestartPolicy.UNLESS_STOPPED.value == "unless-stopped"

    def test_closed_set(self):
        members = set(RestartPolicy.__members__)
        assert members == {"NO", "ON_FAILURE", "ALWAYS", "UNLESS_STOPPED"}

    def test_str_equality(self):
        assert RestartPolicy.NO == "no"

    def test_str_fstring(self):
        assert f"{RestartPolicy.ALWAYS}" == "always"

    def test_strenum_is_str(self):
        assert isinstance(RestartPolicy.ON_FAILURE, str)


class TestNetworkMode:
    def test_is_strenum(self):
        assert issubclass(NetworkMode, StrEnum)

    def test_is_enum(self):
        assert issubclass(NetworkMode, Enum)

    def test_has_bridge(self):
        assert NetworkMode.BRIDGE.value == "bridge"

    def test_has_host(self):
        assert NetworkMode.HOST.value == "host"

    def test_has_none(self):
        assert NetworkMode.NONE.value == "none"

    def test_has_container(self):
        assert NetworkMode.CONTAINER.value == "container"

    def test_closed_set(self):
        members = set(NetworkMode.__members__)
        assert members == {"BRIDGE", "HOST", "NONE", "CONTAINER"}

    def test_str_equality(self):
        assert NetworkMode.BRIDGE == "bridge"

    def test_str_fstring(self):
        assert f"{NetworkMode.HOST}" == "host"

    def test_strenum_is_str(self):
        assert isinstance(NetworkMode.NONE, str)
