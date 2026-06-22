from queue import Queue
from threading import Thread
from collections.abc import Callable, Iterator

from oci_runtime.domain.enums import NetworkMode, RestartPolicy, VolumeMountType
from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ContainerRuntimeError,
    ImageNotFoundError,
)
from oci_runtime.domain.types import ContainerInfo, ExecResult, PruneResult, RunConfig
from oci_runtime.ports.cancellation import CancellationToken
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.managers import ContainerManager
from oci_runtime.ports.parsers import ContainerParser
from oci_runtime.ports.pty_transport import PtyTransport
from oci_runtime.ports.streaming import StreamingTransport
from oci_runtime.ports.transport import Transport
from oci_runtime.ports.output_stream import OutputStream
from oci_runtime.ports.tty import TtyDetector
from oci_runtime.adapters.managers.base import CliBaseManager

_LOGS_JOIN_TIMEOUT = 5.0


class CliContainerManager(CliBaseManager[ContainerParser], ContainerManager):
    _not_found_error = ContainerNotFoundError
    _generic_error = ContainerRuntimeError

    def __init__(
        self,
        transport: Transport,
        parser: ContainerParser,
        caps: RuntimeCapabilities,
        streaming: StreamingTransport,
        tty_detector: TtyDetector,
        *,
        pty_transport: PtyTransport,
        cancellation_factory: Callable[[], CancellationToken],
        output_stream: OutputStream | None = None,
    ):
        super().__init__(transport, parser, caps)
        self._streaming = streaming
        self._tty_detector = tty_detector
        self._pty_transport = pty_transport
        self._cancellation_factory = cancellation_factory
        self._output_stream = output_stream

    def _resolve_tty(self, config: RunConfig) -> bool:
        return config.tty or (config.auto_tty and self._tty_detector.is_tty())

    def run(self, config: RunConfig) -> str:
        effective_tty = self._resolve_tty(config)

        cmd = [self._transport.get_runtime_binary(), "run"]
        cmd.extend(self._caps.default_run_flags)

        if config.detach:
            cmd.append("-d")
        if config.remove:
            cmd.append("--rm")
        if config.name:
            cmd.extend(["--name", config.name])
        if effective_tty:
            cmd.append("-t")
        if config.stdin_open:
            cmd.append("-i")
        if config.user:
            cmd.extend(["-u", config.user])
        if config.working_dir:
            cmd.extend(["-w", config.working_dir])
        if config.hostname:
            cmd.extend(["--hostname", config.hostname])
        if config.entrypoint:
            cmd.extend(["--entrypoint", config.entrypoint])

        if config.network == NetworkMode.CONTAINER:
            cmd.extend(["--network", f"container:{config.network_container}"])
        elif config.network != NetworkMode.BRIDGE:
            cmd.extend(["--network", str(config.network)])

        if config.restart_policy != RestartPolicy.NO:
            cmd.extend(["--restart", str(config.restart_policy)])

        if config.log_driver and self._caps.supports_log_drivers:
            cmd.extend(["--log-driver", config.log_driver])
        if config.privileged:
            cmd.append("--privileged")
        if config.read_only:
            cmd.append("--read-only")
        if config.memory_limit:
            cmd.extend(["-m", config.memory_limit])
        if config.cpu_limit:
            cmd.extend(["--cpus", config.cpu_limit])

        for env_key, env_val in config.environment.items():
            cmd.extend(["-e", f"{env_key}={env_val}"])

        for vol in config.volumes:
            src = str(vol.source)
            tgt = str(vol.target)
            if vol.type is VolumeMountType.TMPFS:
                cmd.extend(["--mount", f"type=tmpfs,target={tgt}"])
            else:
                spec = f"{src}:{tgt}"
                if vol.read_only:
                    spec += ":ro"
                cmd.extend(["-v", spec])

        for port in config.ports:
            if port.host_port is not None:
                cmd.extend(
                    ["-p", f"{port.host_port}:{port.container_port}/{port.protocol}"]
                )
            else:
                cmd.extend(["-p", f"{port.container_port}/{port.protocol}"])

        for k, v in config.labels.items():
            cmd.extend(["-l", f"{k}={v}"])

        cmd.extend(config.runtime_flags)
        cmd.append(config.image)

        if config.command:
            cmd.extend(config.command)

        if effective_tty:
            result = self._pty_transport.execute_pty(
                cmd,
                output_stream=self._output_stream,
                timeout=config.timeout,
            )
            self._check_result(
                result,
                cmd,
                operation="run container",
                entity=config.image,
                not_found=ImageNotFoundError,
            )
            return ""

        result = self._streaming.stream(cmd, timeout=config.timeout)
        self._check_result(
            result,
            cmd,
            operation="run container",
            entity=config.image,
            not_found=ImageNotFoundError,
        )
        if config.stream_output:
            return ""
        return self._decode_bytes(result.stdout).strip()

    def start(self, container: str) -> None:
        cmd = [self._transport.get_runtime_binary(), "start", container]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="start container", entity=container)

    def stop(self, container: str, timeout: int = 10) -> None:
        cmd = [
            self._transport.get_runtime_binary(),
            "stop",
            "-t",
            str(timeout),
            container,
        ]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="stop container", entity=container)

    def restart(self, container: str, timeout: int = 10) -> None:
        cmd = [
            self._transport.get_runtime_binary(),
            "restart",
            "-t",
            str(timeout),
            container,
        ]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="restart container", entity=container)

    def remove(
        self, container: str, force: bool = False, volumes: bool = False
    ) -> None:
        cmd = [self._transport.get_runtime_binary(), "rm", container]
        if force:
            cmd.append("-f")
        if volumes:
            cmd.append("-v")
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="remove container", entity=container)

    def exists(self, container: str) -> bool:
        try:
            self.inspect(container)
            return True
        except ContainerNotFoundError:
            return False

    def inspect(self, container: str) -> ContainerInfo:
        cmd = [
            self._transport.get_runtime_binary(),
            "container",
            "inspect",
            "--format",
            "json",
            container,
        ]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="inspect container", entity=container)
        return self._parser.parse_inspect(self._decode_bytes(result.stdout))

    def list(
        self, show_all: bool = False, filters: dict[str, str] | None = None
    ) -> list[ContainerInfo]:
        cmd = [self._transport.get_runtime_binary(), "container", "list"]
        cmd.extend(self._caps.list_format_flags)
        if show_all:
            cmd.append("-a")
        if filters:
            for key, val in filters.items():
                cmd.extend(["--filter", f"{key}={val}"])
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="list containers", entity="")
        return self._parser.parse_list(self._decode_bytes(result.stdout))

    def logs(
        self, container: str, follow: bool = False, tail: int | None = None
    ) -> Iterator[str]:
        cmd = [self._transport.get_runtime_binary(), "logs", container]
        if follow:
            cmd.append("--follow")
        if tail is not None:
            cmd.extend(["--tail", str(tail)])

        if not follow:
            result = self._transport.execute(cmd)
            self._check_result(result, cmd, operation="get logs", entity=container)
            yield self._decode_bytes(result.stdout)
            return

        cancel_token = self._cancellation_factory()
        queue: Queue[str | None] = Queue()
        errors: list[Exception] = []

        def _on_stdout(data: bytes) -> None:
            queue.put(self._decode_bytes(data))

        def _run() -> None:
            try:
                self._streaming.stream(
                    cmd,
                    on_stdout=_on_stdout,
                    on_stderr=_on_stdout,
                    cancel_token=cancel_token,
                )
            except Exception as e:
                errors.append(e)
            finally:
                queue.put(None)

        thread = Thread(target=_run, daemon=True, name="oci-logs")
        thread.start()

        try:
            while True:
                chunk = queue.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            cancel_token.cancel()
            thread.join(timeout=_LOGS_JOIN_TIMEOUT)
            if errors:
                raise errors[0]

    def exec_container(
        self,
        container: str,
        command: list[str],
        detach: bool = False,
        user: str | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        cmd = [self._transport.get_runtime_binary(), "exec"]
        if detach:
            cmd.append("-d")
        if user:
            cmd.extend(["-u", user])
        cmd.extend([container] + command)
        result = self._transport.execute(cmd, timeout=timeout)
        stderr_str = self._decode_bytes(result.stderr)
        if result.returncode != 0 and self._parser.is_not_found_error(stderr_str):
            raise self._not_found_error(container)
        return ExecResult(
            returncode=result.returncode,
            stdout=self._decode_bytes(result.stdout),
            stderr=stderr_str,
        )

    def prune(self) -> PruneResult:
        cmd = [self._transport.get_runtime_binary(), "container", "prune", "--force"]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="prune containers", entity="")
        return self._parser.parse_prune(self._decode_bytes(result.stdout))
