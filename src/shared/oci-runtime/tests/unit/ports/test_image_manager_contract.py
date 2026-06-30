from abc import ABC, abstractmethod

from oci_runtime.domain.exceptions import ImageNotFoundError
from oci_runtime.domain.types import BuildContext, ImageInfo, PruneResult
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.managers import ImageManager
from oci_runtime.ports.parsers import ImageParser
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.transport import Transport
from tests.helpers.mock_parsers import MockImageParser
from oci_runtime.adapters.helpers.result_checker import CliResultChecker
from oci_runtime.adapters.helpers.list_executor import CliListExecutor
from oci_runtime.domain.exceptions import (
    ImageNotFoundError,
    ImagePullAccessDeniedError,
    ImageRuntimeError,
)
from tests.helpers.mock_transport import (
    RecordingTransport,
    MockResultChecker,
    MockListExecutor,
)


class ImageManagerContractTest(ABC):
    @abstractmethod
    def make_manager(
        self, transport: Transport, parser: ImageParser, caps: RuntimeCapabilities
    ) -> ImageManager: ...

    def _defaults(self):
        t = RecordingTransport("docker")
        caps = RuntimeCapabilities(default_build_flags=("--quiet",))
        return self.make_manager(t, MockImageParser(), caps), t

    def _failing(self, stderr="No such image: nonexistent"):
        cmd = ("docker", "image", "inspect", "--format", "json", "nonexistent")
        t = RecordingTransport(
            "docker",
            responses={
                cmd: RawExecResult(returncode=1, stdout=b"", stderr=stderr.encode()),
            },
        )
        return self.make_manager(t, MockImageParser(), RuntimeCapabilities()), t

    def test_base_is_abstract(self):
        assert ImageManagerContractTest.make_manager.__isabstractmethod__

    def test_make_manager_works(self):
        mgr, _ = self._defaults()
        assert isinstance(mgr, ImageManager)

    def test_build_returns_str(self):
        mgr, t = self._defaults()
        t._responses[("docker", "build", "-t", "myimg", "--quiet", "-")] = (
            RawExecResult(0, b"sha256:abc\n", b"")
        )
        result = mgr.build(BuildContext(build_file_content="FROM alpine"), "myimg")
        assert isinstance(result, str)

    def test_tag_returns_none(self):
        mgr, t = self._defaults()
        t._responses[("docker", "tag", "alpine", "latest")] = RawExecResult(0, b"", b"")
        result = mgr.tag("alpine", "latest")
        assert result is None

    def test_push_returns_none(self):
        mgr, t = self._defaults()
        t._responses[("docker", "push", "alpine")] = RawExecResult(0, b"", b"")
        result = mgr.push("alpine")
        assert result is None

    def test_pull_returns_str(self):
        mgr, t = self._defaults()
        t._responses[("docker", "pull", "alpine")] = RawExecResult(
            0, b"sha256:abc\n", b""
        )
        result = mgr.pull("alpine")
        assert isinstance(result, str)

    def test_remove_returns_none(self):
        mgr, t = self._defaults()
        t._responses[("docker", "rmi", "alpine")] = RawExecResult(0, b"", b"")
        result = mgr.remove("alpine")
        assert result is None

    def test_exists_returns_bool(self):
        mgr, t = self._defaults()
        t._responses[("docker", "image", "inspect", "--format", "json", "alpine")] = (
            RawExecResult(0, b"dummy", b"")
        )
        result = mgr.exists("alpine")
        assert isinstance(result, bool)

    def test_inspect_returns_image_info(self):
        mgr, t = self._defaults()
        t._responses[("docker", "image", "inspect", "--format", "json", "alpine")] = (
            RawExecResult(0, b"dummy", b"")
        )
        result = mgr.inspect("alpine")
        assert isinstance(result, ImageInfo)

    def test_list_returns_list(self):
        mgr, t = self._defaults()
        t._responses[("docker", "image", "list")] = RawExecResult(0, b"dummy", b"")
        result = mgr.list()
        assert isinstance(result, list)

    def test_prune_returns_prune_result(self):
        mgr, t = self._defaults()
        t._responses[("docker", "image", "prune", "--force")] = RawExecResult(
            0, b"", b""
        )
        result = mgr.prune()
        assert isinstance(result, PruneResult)

    def test_inspect_nonexistent_raises_not_found(self):
        mgr, _ = self._failing()
        try:
            mgr.inspect("nonexistent")
            assert False, "Expected ImageNotFoundError"
        except ImageNotFoundError:
            pass

    def test_build_delegates_to_transport(self):
        mgr, t = self._defaults()
        t._responses[("docker", "build", "-t", "myimg", "--quiet", "-")] = (
            RawExecResult(0, b"sha256:abc\n", b"")
        )
        mgr.build(BuildContext(build_file_content="FROM alpine"), "myimg")
        assert len(t.calls) > 0


class TestCliImageManagerContract(ImageManagerContractTest):
    def make_manager(self, transport, parser, caps) -> ImageManager:
        from oci_runtime.adapters.managers.image import CliImageManager

        chk = CliResultChecker(
            generic_error=ImageRuntimeError,
            not_found_error=ImageNotFoundError,
            is_not_found=parser.is_not_found_error,
            auth_error=ImagePullAccessDeniedError,
            is_auth=parser.is_auth_error,
        )
        return CliImageManager(
            transport,
            parser,
            caps,
            result_checker=chk,
            list_executor=CliListExecutor(
                transport, caps, chk, parse_list=parser.parse_list
            ),
        )
