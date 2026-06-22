from pathlib import Path
from unittest.mock import MagicMock

from oci_runtime.adapters.managers.image import CliImageManager
from oci_runtime.domain.types import BuildContext, ImageInfo, PruneResult
from oci_runtime.domain.capabilities import RuntimeCapabilities
from oci_runtime.ports.parsers import ImageParser
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.transport import Transport


class _MockParser(ImageParser):
    def parse_inspect(self, raw: str) -> ImageInfo:
        return ImageInfo(id="sha256:abc")
    def parse_list(self, raw: str) -> list[ImageInfo]:
        return [ImageInfo(id="sha256:abc")]
    def parse_build_output(self, raw: str) -> str:
        return "sha256:abc"
    def parse_id_from_pull(self, raw: str) -> str:
        return "sha256:abc"
    def parse_prune(self, raw: str) -> PruneResult:
        return PruneResult()
    def is_not_found_error(self, stderr: str) -> bool:
        return "No such image" in stderr


class TestCliImageManager:
    def setup_method(self):
        self.transport = MagicMock(spec=Transport)
        self.transport.binary = "docker"
        self.transport.execute.return_value = RawExecResult(returncode=0, stdout=b'[{"Id":"sha256:abc"}]', stderr=b"")
        self.parser = _MockParser()
        self.caps = RuntimeCapabilities()
        self.manager = CliImageManager(self.transport, self.parser, self.caps)

    def test_extends_cli_base_manager(self):
        from oci_runtime.adapters.managers.base import CliBaseManager
        assert isinstance(self.manager, CliBaseManager)

    def test_implements_image_manager(self):
        from oci_runtime.ports.managers import ImageManager
        assert isinstance(self.manager, ImageManager)

    def test_build_calls_transport_execute(self):
        ctx = BuildContext(build_file_content="FROM alpine")
        self.manager.build(ctx, "my-image")
        self.transport.execute.assert_called_once()
        args = self.transport.execute.call_args[0][0]
        assert "build" in args
        assert "-t" in args
        assert "my-image" in args

    def test_build_with_context_path_sends_encoded_dockerfile_via_input_data(self):
        ctx = BuildContext(build_file_content="FROM alpine:latest", context_path=Path("/tmp/build-ctx"))
        result = self.manager.build(ctx, "my-image")
        _, kwargs = self.transport.execute.call_args
        assert kwargs["input_data"] == b"FROM alpine:latest"

    def test_build_with_context_path_includes_f_dash(self):
        ctx = BuildContext(build_file_content="FROM alpine", context_path=Path("/tmp/build-ctx"))
        result = self.manager.build(ctx, "my-image")
        args = self.transport.execute.call_args[0][0]
        assert "-f" in args
        f_idx = args.index("-f")
        assert f_idx + 1 < len(args)
        assert args[f_idx + 1] == "-"

    def test_build_returns_image_id(self):
        ctx = BuildContext(build_file_content="FROM alpine")
        result = self.manager.build(ctx, "my-image")
        assert result == "sha256:abc"

    def test_inspect_calls_transport(self):
        self.manager.inspect("alpine")
        self.transport.execute.assert_called_once()

    def test_list_calls_transport(self):
        self.manager.list()
        self.transport.execute.assert_called_once()

    def test_exists_true(self):
        assert self.manager.exists("alpine") is True

    def test_exists_false(self):
        self.transport.execute.return_value = RawExecResult(returncode=1, stdout=b"", stderr=b"No such image: alpine")
        assert self.manager.exists("nonexistent") is False

    def test_create_tar_is_deterministic(self):
        from oci_runtime.adapters._tar import create_build_tar
        tar1 = create_build_tar("FROM alpine", {"app.py": b"print('hi')"})
        tar2 = create_build_tar("FROM alpine", {"app.py": b"print('hi')"})
        assert tar1 == tar2
