from unittest.mock import MagicMock, patch

import pytest

from oci_runtime.adapters.managers.container import CliContainerManager
from oci_runtime.domain.enums import NetworkMode
from oci_runtime.domain.exceptions import ContainerRuntimeError, ImageNotFoundError
from oci_runtime.domain.types import ContainerInfo, PortMapping, RunConfig, VolumeMount
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.parsers import ContainerParser
from oci_runtime.domain.types import ExecResult
from oci_runtime.ports.transport import Transport


class _MockParser(ContainerParser):
    def parse_inspect(self, raw: str) -> ContainerInfo:
        return ContainerInfo(id="abc", name="c1", image="alpine", state="running", status="Up")
    def parse_list(self, raw: str) -> list[ContainerInfo]:
        return [ContainerInfo(id="abc", name="c1", image="alpine", state="running", status="Up")]
    def parse_prune(self, raw: str) -> dict[str, int]:
        return {"deleted": 0, "reclaimed_bytes": 0}
    def is_not_found_error(self, stderr: str) -> bool:
        return "No such container" in stderr


class TestCliContainerManager:
    def setup_method(self):
        self.transport = MagicMock(spec=Transport)
        self.transport.binary = "docker"
        self.transport.execute.return_value = ExecResult(returncode=0, stdout=b"abc123", stderr=b"")
        self.parser = _MockParser()
        self.caps = RuntimeCapabilities()
        self.manager = CliContainerManager(self.transport, self.parser, self.caps)

    def test_run_calls_transport_execute(self):
        config = RunConfig(image="alpine", command=["echo", "hi"])
        self.manager.run(config)
        self.transport.execute.assert_called_once()

    def test_run_includes_image_and_command(self):
        config = RunConfig(image="alpine", command=["echo", "hi"])
        self.manager.run(config)
        args = self.transport.execute.call_args[0][0]
        assert "alpine" in args
        assert "echo" in args
        assert "hi" in args

    def test_run_adds_default_run_flags_from_caps(self):
        caps = RuntimeCapabilities(default_run_flags=["--userns=keep-id"])
        manager = CliContainerManager(self.transport, self.parser, caps)
        config = RunConfig(image="alpine")
        manager.run(config)
        args = self.transport.execute.call_args[0][0]
        assert "--userns=keep-id" in args

    def test_check_result_raises_not_found(self):
        with pytest.raises(ImageNotFoundError, match="my-image"):
            self.manager._check_result(
                ExecResult(returncode=1, stdout=b"", stderr=b"No such container: x"),
                cmd=["docker", "run", "my-image"],
                entity="my-image",
                not_found=ImageNotFoundError,
            )

    def test_check_result_lacks_is_not_found_error_raises_attribute_error(self):
        with pytest.raises(AttributeError, match="is_not_found_error"):
            manager = CliContainerManager(self.transport, object(), self.caps)
            manager._check_result(
                ExecResult(returncode=1, stdout=b"", stderr=b"any error"),
                cmd=["docker", "run", "x"],
                entity="x",
                not_found=ImageNotFoundError,
            )

    def test_list_calls_transport(self):
        self.manager.list()
        self.transport.execute.assert_called_once()

    def test_run_network_bridge_ignores_container_arg(self):
        config = RunConfig(image="alpine", network=NetworkMode.BRIDGE, network_container="nginx")
        self.manager.run(config)
        args = self.transport.execute.call_args[0][0]
        assert "--network" not in args

    def test_run_network_host_adds_flag(self):
        config = RunConfig(image="alpine", network=NetworkMode.HOST)
        self.manager.run(config)
        args = self.transport.execute.call_args[0][0]
        idx = args.index("--network")
        assert args[idx + 1] == "host"

    def test_run_network_container_requires_arg(self):
        config = RunConfig(image="alpine", network=NetworkMode.CONTAINER)
        with pytest.raises(ContainerRuntimeError, match="network_container"):
            self.manager.run(config)

    def test_run_network_container_adds_flag(self):
        config = RunConfig(
            image="alpine", network=NetworkMode.CONTAINER, network_container="nginx"
        )
        self.manager.run(config)
        args = self.transport.execute.call_args[0][0]
        idx = args.index("--network")
        assert args[idx + 1] == "container:nginx"

    def test_run_network_none_adds_flag(self):
        config = RunConfig(image="alpine", network=NetworkMode.NONE)
        self.manager.run(config)
        args = self.transport.execute.call_args[0][0]
        idx = args.index("--network")
        assert args[idx + 1] == "none"
