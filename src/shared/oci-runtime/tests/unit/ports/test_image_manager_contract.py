from abc import ABC, abstractmethod

from oci_runtime.domain.exceptions import ImageNotFoundError
from oci_runtime.domain.types import BuildContext, ImageInfo
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.managers import ImageManager
from oci_runtime.ports.parsers import ImageParser
from oci_runtime.domain.types import ExecResult
from oci_runtime.ports.transport import Transport
from tests.helpers.mock_parsers import MockImageParser
from tests.helpers.mock_transport import FailingTransport, RecordingTransport


class ImageManagerContractTest(ABC):
    @abstractmethod
    def make_manager(self, transport: Transport, parser: ImageParser, caps: RuntimeCapabilities) -> ImageManager:
        ...

    def _defaults(self):
        t = RecordingTransport("docker")
        caps = RuntimeCapabilities(default_build_flags=["--quiet"])
        return self.make_manager(t, MockImageParser(), caps), t

    def _failing(self, stderr="No such image: nonexistent"):
        t = FailingTransport("docker", stderr=stderr)
        return self.make_manager(t, MockImageParser(), RuntimeCapabilities()), t

    def test_base_is_abstract(self):
        assert ImageManagerContractTest.make_manager.__isabstractmethod__

    def test_make_manager_works(self):
        mgr, _ = self._defaults()
        assert isinstance(mgr, ImageManager)

    def test_build_returns_str(self):
        mgr, t = self._defaults()
        t._responses["docker build -t myimg - --quiet"] = ExecResult(0, b"sha256:abc\n", b"")
        result = mgr.build(BuildContext(build_file_content="FROM alpine"), "myimg")
        assert isinstance(result, str)

    def test_tag_returns_none(self):
        mgr, t = self._defaults()
        t._responses["docker tag alpine latest"] = ExecResult(0, b"", b"")
        result = mgr.tag("alpine", "latest")
        assert result is None

    def test_push_returns_none(self):
        mgr, t = self._defaults()
        t._responses["docker push alpine"] = ExecResult(0, b"", b"")
        result = mgr.push("alpine")
        assert result is None

    def test_pull_returns_str(self):
        mgr, t = self._defaults()
        t._responses["docker pull alpine"] = ExecResult(0, b"sha256:abc\n", b"")
        result = mgr.pull("alpine")
        assert isinstance(result, str)

    def test_remove_returns_none(self):
        mgr, t = self._defaults()
        t._responses["docker rmi alpine"] = ExecResult(0, b"", b"")
        result = mgr.remove("alpine")
        assert result is None

    def test_exists_returns_bool(self):
        mgr, t = self._defaults()
        t._responses["docker image inspect --format json alpine"] = ExecResult(0, b"dummy", b"")
        result = mgr.exists("alpine")
        assert isinstance(result, bool)

    def test_inspect_returns_image_info(self):
        mgr, t = self._defaults()
        t._responses["docker image inspect --format json alpine"] = ExecResult(0, b"dummy", b"")
        result = mgr.inspect("alpine")
        assert isinstance(result, ImageInfo)

    def test_list_returns_list(self):
        mgr, t = self._defaults()
        t._responses["docker image list"] = ExecResult(0, b"dummy", b"")
        result = mgr.list()
        assert isinstance(result, list)

    def test_prune_returns_dict(self):
        mgr, t = self._defaults()
        t._responses["docker image prune --force"] = ExecResult(0, b"", b"")
        result = mgr.prune()
        assert isinstance(result, dict)

    def test_inspect_nonexistent_raises_not_found(self):
        mgr, _ = self._failing()
        try:
            mgr.inspect("nonexistent")
            assert False, "Expected ImageNotFoundError"
        except ImageNotFoundError:
            pass

    def test_build_delegates_to_transport(self):
        mgr, t = self._defaults()
        t._responses["docker build -t myimg - --quiet"] = ExecResult(0, b"sha256:abc\n", b"")
        mgr.build(BuildContext(build_file_content="FROM alpine"), "myimg")
        assert len(t.calls) > 0


class TestCliImageManagerContract(ImageManagerContractTest):
    def make_manager(self, transport, parser, caps) -> ImageManager:
        from oci_runtime.adapters.managers.image import CliImageManager
        return CliImageManager(transport, parser, caps)
