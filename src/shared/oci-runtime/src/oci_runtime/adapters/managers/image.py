from oci_runtime.adapters._tar import create_build_tar
from oci_runtime.domain.exceptions import (
    ImageError,
    ImageNotFoundError,
    ImageRuntimeError,
)
from oci_runtime.domain.types import PruneResult, BuildContext, ImageInfo
from oci_runtime.domain.capabilities import RuntimeCapabilities
from oci_runtime.ports.managers import ImageManager
from oci_runtime.ports.parsers import ImageParser
from oci_runtime.ports.transport import Transport
from oci_runtime.adapters.managers.base import CliBaseManager


class CliImageManager(CliBaseManager[ImageParser], ImageManager):
    _not_found_error = ImageNotFoundError
    _generic_error = ImageRuntimeError
    def __init__(self, transport: Transport, parser: ImageParser, caps: RuntimeCapabilities):
        super().__init__(transport, parser, caps)

    def build(self, context: BuildContext, image_name: str, timeout: int = 600) -> str:
        cmd = [self._transport.get_runtime_binary(), "build", "-t", image_name]
        input_data = None

        if context.build_file_path is not None:
            cmd.extend(["-f", str(context.build_file_path)])
            cmd.append(str(context.context_path or context.build_file_path.parent))
        elif context.context_path is not None:
            cmd.extend(["-f", "-"])
            cmd.append(str(context.context_path))
            input_data = context.build_file_content.encode("utf-8")
        else:
            input_data = create_build_tar(context.build_file_content, context.files, self._caps.tar_entry_name)
            cmd.append("-")

        cmd.extend(self._caps.default_build_flags)
        if context.no_cache:
            cmd.append("--no-cache")
        if context.target:
            cmd.extend(["--target", context.target])
        for k, v in context.build_args.items():
            cmd.extend(["--build-arg", f"{k}={v}"])
        for k, v in context.labels.items():
            cmd.extend(["--label", f"{k}={v}"])
        if context.pull:
            cmd.append("--pull")
        if not context.rm:
            cmd.extend(["--rm", "false"])
        if context.network:
            cmd.extend(["--network", context.network])
        for k, v in context.build_contexts.items():
            cmd.extend(["--build-context", f"{k}={v}"])

        result = self._transport.execute(cmd, input_data=input_data, timeout=timeout)
        self._check_result(result, cmd, operation="build image", entity=image_name)
        ident = self._parser.parse_build_output(self._decode_bytes(result.stdout))
        if not ident or ident == "sha256:":
            raise ImageError(message="Could not parse image id from build output", stderr=self._decode_bytes(result.stdout))
        return ident

    def tag(self, image: str, tag: str) -> None:
        cmd = [self._transport.get_runtime_binary(), "tag", image, tag]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="tag image", entity=image)

    def push(self, image: str, timeout: int = 300) -> None:
        cmd = [self._transport.get_runtime_binary(), "push", image]
        result = self._transport.execute(cmd, timeout=timeout)
        self._check_result(result, cmd, operation="push image", entity=image)

    def pull(self, image: str, timeout: int = 300) -> str:
        cmd = [self._transport.get_runtime_binary(), "pull", image]
        result = self._transport.execute(cmd, timeout=timeout)
        self._check_result(result, cmd, operation="pull image", entity=image)
        ident = self._parser.parse_id_from_pull(self._decode_bytes(result.stdout))
        if not ident:
            raise ImageError(message="Could not parse image id from pull output", stderr=self._decode_bytes(result.stdout))
        return ident

    def remove(self, image: str, force: bool = False) -> None:
        cmd = [self._transport.get_runtime_binary(), "rmi", image]
        if force:
            cmd.append("--force")
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="remove image", entity=image)

    def exists(self, image: str) -> bool:
        try:
            self.inspect(image)
            return True
        except ImageNotFoundError:
            return False

    def inspect(self, image: str) -> ImageInfo:
        cmd = [self._transport.get_runtime_binary(), "image", "inspect", "--format", "json", image]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="inspect image", entity=image)
        return self._parser.parse_inspect(self._decode_bytes(result.stdout))

    def list(self, filters: dict[str, str] | None = None) -> list[ImageInfo]:
        cmd = [self._transport.get_runtime_binary(), "image", "list"]
        cmd.extend(self._caps.list_format_flags)
        if filters:
            for key, val in filters.items():
                cmd.extend(["--filter", f"{key}={val}"])
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="list images", entity="")
        return self._parser.parse_list(self._decode_bytes(result.stdout))

    def prune(self, show_all: bool = False) -> PruneResult:
        cmd = [self._transport.get_runtime_binary(), "image", "prune", "--force"]
        if show_all:
            cmd.append("--all")
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="prune images", entity="")
        return self._parser.parse_prune(self._decode_bytes(result.stdout))
