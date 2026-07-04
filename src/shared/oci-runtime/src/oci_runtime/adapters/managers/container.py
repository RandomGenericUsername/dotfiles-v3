import warnings
from queue import Queue
from threading import Thread
from collections.abc import Callable, Iterator

from oci_runtime.adapters.managers._timeouts import cli_seconds
from oci_runtime.adapters.transport.cancel import _CancelContext
from oci_runtime.adapters.transport.runner import _SubprocessRunner
from oci_runtime.adapters.transport.stream import _AsyncStreamReader
from oci_runtime.domain.encoding import safe_decode
from oci_runtime.domain.enums import (
    NetworkMode,
    RestartPolicy,
    Subcommand,
    VolumeMountType,
)
from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ImageNotFoundError,
    OciError,
)
from oci_runtime.domain.types import ContainerInfo, ExecResult, PruneResult, RunConfig
from oci_runtime.ports.cancellation import CancellationToken
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.list_executor import ListExecutor
from oci_runtime.ports.managers import ContainerManager
from oci_runtime.ports.parsers import ContainerParser
from oci_runtime.ports.pty_transport import PtyTransport
from oci_runtime.ports.result_checker import ResultChecker
from oci_runtime.ports.streaming import StreamingTransport
from oci_runtime.ports.transport import Transport
from oci_runtime.ports.output_stream import OutputStream
from oci_runtime.ports.tty import TtyDetector

_LOGS_JOIN_TIMEOUT = 5.0
_DEFAULT_STOP_TIMEOUT_SECONDS = 10


class LogDriverNotSupportedWarning(UserWarning):
    """Emitted when a log driver is configured but the runtime does not support it."""


class CliContainerManager(ContainerManager):
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
        result_checker: ResultChecker,
        list_executor: ListExecutor[ContainerInfo],
    ):
        self._transport = transport
        self._parser = parser
        self._caps = caps
        self._streaming = streaming
        self._tty_detector = tty_detector
        self._pty_transport = pty_transport
        self._cancellation_factory = cancellation_factory
        self._output_stream = output_stream
        self._result_checker = result_checker
        self._list_executor = list_executor

    def _resolve_tty(self, config: RunConfig) -> bool:
        return config.tty or (config.auto_tty and self._tty_detector.is_tty())

    def run(self, config: RunConfig) -> str:
        effective_tty = self._resolve_tty(config)

        cmd = [self._transport.get_runtime_binary(), Subcommand.RUN.value]
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
        else:
            cmd.extend(["--network", str(config.network)])

        if config.restart_policy != RestartPolicy.NO:
            cmd.extend(["--restart", str(config.restart_policy)])

        if config.log_driver:
            if self._caps.supports_log_drivers:
                cmd.extend(["--log-driver", config.log_driver])
            else:
                warnings.warn(
                    LogDriverNotSupportedWarning(
                        f"Log driver {config.log_driver!r} configured but not supported"
                    )
                )
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
            proto = port.protocol or "tcp"
            if port.host_ip is not None:
                if port.host_port is not None:
                    flag = (
                        f"{port.host_ip}:{port.host_port}:{port.container_port}/{proto}"
                    )
                else:
                    flag = f"{port.host_ip}::{port.container_port}/{proto}"
            else:
                if port.host_port is not None:
                    flag = f"{port.host_port}:{port.container_port}/{proto}"
                else:
                    flag = str(port.container_port)
            cmd.extend(["-p", flag])

        for k, v in config.labels.items():
            cmd.extend(["-l", f"{k}={v}"])

        cmd.extend(config.runtime_flags)
        cmd.append(config.image)

        if config.command:
            cmd.extend(config.command)

        if effective_tty:
            if self._output_stream is None:
                raise OciError("output_stream required for TTY run")
            result = self._pty_transport.execute_pty(
                cmd,
                output_stream=self._output_stream,
                timeout=config.timeout,
            )
            self._result_checker.check(
                result,
                cmd,
                operation="run container",
                entity=config.image,
                not_found_error=ImageNotFoundError,
            )
            return ""

        if config.stream_output:
            output_stream = self._output_stream

            def _write(data: bytes) -> None:
                if output_stream is not None:
                    output_stream.write(data)

            result = self._streaming.stream(
                cmd,
                on_stdout=_write,
                on_stderr=_write,
                timeout=config.timeout,
            )
            self._result_checker.check(
                result,
                cmd,
                operation="run container",
                entity=config.image,
                not_found_error=ImageNotFoundError,
            )
            return safe_decode(result.stdout).strip()

        result = self._streaming.stream(cmd, timeout=config.timeout)
        self._result_checker.check(
            result,
            cmd,
            operation="run container",
            entity=config.image,
            not_found_error=ImageNotFoundError,
        )
        return safe_decode(result.stdout).strip()

    def start(self, container: str) -> None:
        cmd = [self._transport.get_runtime_binary(), Subcommand.START.value, container]
        result = self._transport.execute(cmd)
        self._result_checker.check(
            result, cmd, operation="start container", entity=container
        )

    def stop(self, container: str, timeout: float | None = 10.0) -> None:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.STOP.value,
            "-t",
            cli_seconds(timeout, default=_DEFAULT_STOP_TIMEOUT_SECONDS),
            container,
        ]
        result = self._transport.execute(cmd)
        self._result_checker.check(
            result, cmd, operation="stop container", entity=container
        )

    def restart(self, container: str, timeout: float | None = 10.0) -> None:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.RESTART.value,
            "-t",
            cli_seconds(timeout, default=_DEFAULT_STOP_TIMEOUT_SECONDS),
            container,
        ]
        result = self._transport.execute(cmd)
        self._result_checker.check(
            result, cmd, operation="restart container", entity=container
        )

    def remove(
        self, container: str, force: bool = False, volumes: bool = False
    ) -> None:
        cmd = [self._transport.get_runtime_binary(), Subcommand.RM.value, container]
        if force:
            cmd.append("-f")
        if volumes:
            cmd.append("-v")
        result = self._transport.execute(cmd)
        self._result_checker.check(
            result, cmd, operation="remove container", entity=container
        )

    def exists(self, container: str) -> bool:
        try:
            self.inspect(container)
            return True
        except ContainerNotFoundError:
            return False

    def inspect(self, container: str) -> ContainerInfo:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.CONTAINER.value,
            Subcommand.INSPECT.value,
            "--format",
            "json",
            container,
        ]
        result = self._transport.execute(cmd)
        self._result_checker.check(
            result, cmd, operation="inspect container", entity=container
        )
        return self._parser.parse_inspect(safe_decode(result.stdout))

    def list(
        self, show_all: bool = False, filters: dict[str, str] | None = None
    ) -> list[ContainerInfo]:
        return self._list_executor.execute_list(
            [Subcommand.CONTAINER.value, Subcommand.LIST.value],
            "containers",
            show_all=show_all,
            filters=filters,
        )

    def logs(
        self,
        container: str,
        follow: bool = False,
        tail: int | None = None,
        timeout: float | None = None,
    ) -> Iterator[str]:
        cmd = [self._transport.get_runtime_binary(), Subcommand.LOGS.value, container]
        if follow:
            cmd.append("--follow")
        if tail is not None:
            cmd.extend(["--tail", str(tail)])

        if not follow:
            result = self._transport.execute(cmd)
            self._result_checker.check(
                result, cmd, operation="get logs", entity=container
            )
            yield safe_decode(result.stdout)
            return

        cancel_token = self._cancellation_factory()
        cancel_ctx = _CancelContext(cancel_token)

        runner = _SubprocessRunner(cmd)
        runner.start_stdin_writer()

        reader = _AsyncStreamReader(
            runner.process.stdout.fileno(),
            runner.process.stderr.fileno(),
        )

        queue: Queue[str | None] = Queue()
        errors: list[Exception] = []

        def _on_stdout(data: bytes) -> None:
            queue.put(safe_decode(data))

        def _run() -> None:
            try:
                reader.read(
                    on_stdout=_on_stdout,
                    on_stderr=_on_stdout,
                    cancel_ctx=cancel_ctx,
                    timeout=timeout,
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
            cancel_ctx.cancel()
            thread.join(timeout=_LOGS_JOIN_TIMEOUT)
            if errors and not isinstance(errors[0], GeneratorExit):
                raise errors[0]

    def exec_container(
        self,
        container: str,
        command: list[str],
        detach: bool = False,
        user: str | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        cmd = [self._transport.get_runtime_binary(), Subcommand.EXEC.value]
        if detach:
            cmd.append("-d")
        if user:
            cmd.extend(["-u", user])
        cmd.extend([container] + command)
        result = self._transport.execute(cmd, timeout=timeout)
        try:
            self._result_checker.check(
                result,
                cmd,
                operation="exec in container",
                entity=container,
                not_found_error=ContainerNotFoundError,
            )
        except ContainerNotFoundError:
            pass
        return ExecResult(
            returncode=result.returncode,
            stdout=safe_decode(result.stdout),
            stderr=safe_decode(result.stderr),
        )

    def prune(self) -> PruneResult:
        cmd = [
            self._transport.get_runtime_binary(),
            Subcommand.CONTAINER.value,
            Subcommand.PRUNE.value,
            "--force",
        ]
        result = self._transport.execute(cmd)
        self._result_checker.check(result, cmd, operation="prune containers", entity="")
        return self._parser.parse_prune(safe_decode(result.stdout))
