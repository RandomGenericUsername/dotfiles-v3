from oci_runtime.domain.build_tar import create_build_tar
from oci_runtime.domain.encoding import safe_decode
from oci_runtime.domain.enums import Subcommand
from oci_runtime.domain.exceptions import (
    ImageNotFoundError,
    ImageRuntimeError,
)
from oci_runtime.domain.types import PruneResult, BuildContext, ImageInfo
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.list_executor import ListExecutor
from oci_runtime.ports.managers import ImageManager
from oci_runtime.ports.parsers import ImageParser, ParsingError
from oci_runtime.ports.result_checker import ResultChecker
from oci_runtime.ports.transport import Transport


class CliImageManager(ImageManager):
    def __init__(
        self,
        transport: Transport,
        parser: ImageParser,
        caps: RuntimeCapabilities,
        *,
        result_checker: ResultChecker,
        list_executor: ListExecutor[ImageInfo],
    ):
        self._transport = transport
        self._parser = parser
        self._caps = caps
        self._result_checker = result_checker
        self._list_executor = list_executor

    def build(
        self, context: BuildContext, image_name: str, timeout: float | None = 600.0
    ) -> str:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.BUILD.value,
            "-t",
            image_name,
        ]
        input_data = None
        positional = "."

        if context.build_file_path is not None:
            cmd.extend(["-f", str(context.build_file_path)])
            positional = str(context.context_path or context.build_file_path.parent)
        elif context.context_path is not None:
            cmd.extend(["-f", "-"])
            positional = str(context.context_path)
            if context.build_file_content is None:
                raise ImageRuntimeError(
                    message="BuildContext.build_file_content required for stdin (-f -)"
                )
            input_data = context.build_file_content.encode("utf-8")
        else:
            if context.build_file_content is None:
                raise ImageRuntimeError(
                    message="BuildContext.build_file_content or build_file_path required"
                )
            input_data = create_build_tar(
                context.build_file_content, context.files, self._caps.tar_entry_name
            )
            positional = "-"

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
        for bck, bcv in context.build_contexts.items():
            cmd.extend(["--build-context", f"{bck}={bcv}"])

        cmd.append(positional)
        result = self._transport.execute(cmd, input_data=input_data, timeout=timeout)
        self._result_checker.check(
            result, cmd, operation="build image", entity=image_name
        )
        try:
            ident = self._parser.parse_build_output(safe_decode(result.stdout))
        except ParsingError as e:
            raise ImageRuntimeError(
                message=f"Could not parse image id from build output: {e.message}",
                stderr=safe_decode(result.stdout),
            ) from e
        return ident

    def tag(self, image: str, tag: str) -> None:
        cmd = [self._transport.get_runtime_binary(), Subcommand.TAG.value, image, tag]
        result = self._transport.execute(cmd)
        self._result_checker.check(result, cmd, operation="tag image", entity=image)

    def push(self, image: str, timeout: float | None = 300.0) -> None:
        cmd = [self._transport.get_runtime_binary(), Subcommand.PUSH.value, image]
        result = self._transport.execute(cmd, timeout=timeout)
        self._result_checker.check(result, cmd, operation="push image", entity=image)

    def pull(self, image: str, timeout: float | None = 300.0) -> str:
        cmd = [self._transport.get_runtime_binary(), Subcommand.PULL.value, image]
        result = self._transport.execute(cmd, timeout=timeout)
        self._result_checker.check(result, cmd, operation="pull image", entity=image)
        ident = self._parser.parse_digest_from_pull(safe_decode(result.stdout))
        if not ident:
            raise ImageRuntimeError(
                message="Could not parse image id from pull output",
                stderr=safe_decode(result.stdout),
            )
        return ident

    def remove(self, image: str, force: bool = False) -> None:
        cmd = [self._transport.get_runtime_binary(), Subcommand.RMI.value, image]
        if force:
            cmd.append("--force")
        result = self._transport.execute(cmd)
        self._result_checker.check(result, cmd, operation="remove image", entity=image)

    def exists(self, image: str) -> bool:
        try:
            self.inspect(image)
            return True
        except ImageNotFoundError:
            return False

    def inspect(self, image: str) -> ImageInfo:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.IMAGE.value,
            Subcommand.INSPECT.value,
            "--format",
            "json",
            image,
        ]
        result = self._transport.execute(cmd)
        self._result_checker.check(result, cmd, operation="inspect image", entity=image)
        return self._parser.parse_inspect(safe_decode(result.stdout))

    def list(self, filters: dict[str, str] | None = None) -> list[ImageInfo]:
        return self._list_executor.execute_list(
            [Subcommand.IMAGE.value, Subcommand.LIST.value],
            "images",
            show_all=False,
            filters=filters,
        )

    def prune(self, show_all: bool = False) -> PruneResult:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.IMAGE.value,
            Subcommand.PRUNE.value,
            "--force",
        ]
        if show_all:
            cmd.append("--all")
        result = self._transport.execute(cmd)
        self._result_checker.check(result, cmd, operation="prune images", entity="")
        return self._parser.parse_prune(safe_decode(result.stdout))
