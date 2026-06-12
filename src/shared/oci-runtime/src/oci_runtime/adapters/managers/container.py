from queue import Queue
from threading import Thread
from typing import Iterator

from oci_runtime.domain.enums import NetworkMode, RestartPolicy
from oci_runtime.adapters.parser.exceptions import ParsingError
from oci_runtime.domain.exceptions import (
    ContainerNotFoundError,
    ContainerRuntimeError,
    ImageNotFoundError,
)
from oci_runtime.domain.types import ContainerInfo, ExecOutput, RunConfig
from oci_runtime.ports.capabilities import RuntimeCapabilities
from oci_runtime.ports.managers import ContainerManager
from oci_runtime.ports.parsers import ContainerParser
from oci_runtime.ports.transport import Transport
from oci_runtime.adapters.managers.base import CliBaseManager


class CliContainerManager(CliBaseManager[ContainerParser], ContainerManager):
    def __init__(self, transport: Transport, parser: ContainerParser, caps: RuntimeCapabilities):
        super().__init__(transport, parser, caps)

    def run(self, config: RunConfig) -> str:
        if config.detach and config.effective_tty:
            raise ContainerRuntimeError(
                "detach=True and tty/auto_tty are mutually exclusive: "
                "a detached container has no terminal to attach a PTY to",
            )

        cmd = [self._transport.get_runtime_binary(), "run"]
        cmd.extend(self._caps.default_run_flags)

        if config.detach:
            cmd.append("-d")
        if config.remove:
            cmd.append("--rm")
        if config.name:
            cmd.extend(["--name", config.name])
        if config.effective_tty:
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
            cmd.extend(["--entrypoint", config.entrypoint[0]])
        
        if config.network:
            if config.network == NetworkMode.CONTAINER:
                if not config.network_container:
                    raise ContainerRuntimeError(
                        "network=CONTAINER requires network_container to be set",
                    )
                cmd.extend(["--network", f"container:{config.network_container}"])
            elif config.network != NetworkMode.BRIDGE:
                cmd.extend(["--network", str(config.network)])
        
        if config.restart_policy:
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
            spec = f"{src}:{tgt}"
            if vol.read_only:
                spec += ":ro"
            cmd.extend(["-v", spec])

        for port in config.ports:
            if port.host_port is not None:
                cmd.extend(["-p", f"{port.host_port}:{port.container_port}/{port.protocol}"])
            else:
                cmd.extend(["-p", f"{port.container_port}/{port.protocol}"])

        for k, v in config.labels.items():
            cmd.extend(["-l", f"{k}={v}"])

        cmd.extend(config.runtime_flags)
        cmd.append(config.image)
        
        # Extra entrypoint arguments must follow the image name
        if config.entrypoint and len(config.entrypoint) > 1:
            cmd.extend(config.entrypoint[1:])

        if config.command:
            cmd.extend(config.command)

        if config.effective_tty:
            self._transport.execute_pty(cmd)
            return ""

        result = self._transport.execute(cmd, stream=config.stream_output)
        self._check_result(result, cmd, operation="run container", entity=config.image, not_found=ImageNotFoundError)
        if config.stream_output:
            return ""
        return self._decode_stdout(result.stdout).strip()

    def start(self, container: str) -> None:
        cmd = [self._transport.get_runtime_binary(), "start", container]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="start container", entity=container, not_found=ContainerNotFoundError)

    def stop(self, container: str, timeout: int = 10) -> None:
        cmd = [self._transport.get_runtime_binary(), "stop", "-t", str(timeout), container]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="stop container", entity=container, not_found=ContainerNotFoundError)

    def restart(self, container: str, timeout: int = 10) -> None:
        cmd = [self._transport.get_runtime_binary(), "restart", "-t", str(timeout), container]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="restart container", entity=container, not_found=ContainerNotFoundError)

    def remove(self, container: str, force: bool = False, volumes: bool = False) -> None:
        cmd = [self._transport.get_runtime_binary(), "rm", container]
        if force:
            cmd.append("-f")
        if volumes:
            cmd.append("-v")
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="remove container", entity=container, not_found=ContainerNotFoundError)

    def exists(self, container: str) -> bool:
        try:
            self.inspect(container)
            return True
        except (ContainerNotFoundError, ParsingError):
            return False

    def inspect(self, container: str) -> ContainerInfo:
        cmd = [self._transport.get_runtime_binary(), "container", "inspect", "--format", "json", container]
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="inspect container", entity=container, not_found=ContainerNotFoundError)
        return self._parser.parse_inspect(self._decode_stdout(result.stdout))

    def list(self, show_all: bool = False, filters: dict[str, str] | None = None) -> list[ContainerInfo]:
        cmd = [self._transport.get_runtime_binary(), "container", "list"]
        cmd.extend(self._caps.list_format_flags)
        if show_all:
            cmd.append("-a")
        if filters:
            for key, val in filters.items():
                cmd.extend(["--filter", f"{key}={val}"])
        result = self._transport.execute(cmd)
        return self._parser.parse_list(self._decode_stdout(result.stdout))

    def logs(self, container: str, follow: bool = False, tail: int | None = None) -> Iterator[str]:
        cmd = [self._transport.get_runtime_binary(), "logs", container]
        if follow:
            cmd.append("--follow")
        if tail is not None:
            cmd.extend(["--tail", str(tail)])

        if not follow:
            result = self._transport.execute(cmd)
            self._check_result(result, cmd, operation="get logs", entity=container, not_found=ContainerNotFoundError)
            yield self._decode_stdout(result.stdout)
            return

        queue: Queue[str | None] = Queue()
        errors: list[BaseException] = []

        def _on_output(data: bytes, stream: str) -> None:
            queue.put(self._decode_stdout(data))

        def _run() -> None:
            try:
                self._transport.execute(cmd, stream=True, on_output=_on_output)
            except BaseException as e:
                errors.append(e)
            finally:
                queue.put(None)

        Thread(target=_run, daemon=True, name="oci-logs").start()

        while True:
            chunk = queue.get()
            if chunk is None:
                break
            yield chunk

        if errors:
            raise errors[0]

    def exec_container(self, container: str, command: list[str], detach: bool = False, user: str | None = None) -> ExecOutput:
        cmd = [self._transport.get_runtime_binary(), "exec"]
        if detach:
            cmd.append("-d")
        if user:
            cmd.extend(["-u", user])
        cmd.append(container)
        cmd.extend(command)
        result = self._transport.execute(cmd)
        self._check_result(result, cmd, operation="exec in container", entity=container, not_found=ContainerNotFoundError)
        return ExecOutput(
            returncode=result.returncode,
            stdout=self._decode_stdout(result.stdout),
            stderr=self._decode_stdout(result.stderr),
        )

    def prune(self) -> dict[str, int]:
        cmd = [self._transport.get_runtime_binary(), "container", "prune", "--force"]
        result = self._transport.execute(cmd)
        return self._parser.parse_prune(self._decode_stdout(result.stdout))
