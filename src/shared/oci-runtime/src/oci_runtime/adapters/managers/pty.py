import os
import pty
import select
import shutil
import subprocess
import time

from oci_runtime.domain.exceptions import ContainerRuntimeError, OperationTimeoutError, RuntimeNotAvailableError
from oci_runtime.ports.output_stream import OutputStream


def run_pty(
    command: list[str],
    output_stream: OutputStream | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    """Run a command in a PTY, writing output to output_stream as it arrives.

    When output_stream is None, defaults to writing to sys.stdout.buffer
    via ``StdoutBufferStream``.
    """
    if not command:
        raise ContainerRuntimeError("Empty command list", command=command)
    runtime = command[0]
    if not shutil.which(runtime):
        raise RuntimeNotAvailableError(runtime)

    if output_stream is None:
        from oci_runtime.adapters.output_stream import StdoutBufferStream
        output_stream = StdoutBufferStream()

    output_buffer = bytearray()

    def _on_output(data: bytes) -> None:
        output_stream.write(data)
        output_stream.flush()
        output_buffer.extend(data)

    master_fd, slave_fd = pty.openpty()
    proc = None
    try:
        try:
            proc = subprocess.Popen(
                command,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
            )
        except OSError as e:
            raise ContainerRuntimeError(
                f"PTY process failed to start: {e}", command=command,
            )
        os.close(slave_fd)
        slave_fd = -1

        start = time.monotonic()
        drain_after_exit = False
        while True:
            remaining = None
            if timeout is not None:
                remaining = max(0.0, timeout - (time.monotonic() - start))
                if remaining == 0:
                    proc.kill()
                    proc.wait()
                    raise OperationTimeoutError(command=command, timeout=timeout)
            try:
                r, _, _ = select.select([master_fd], [], [], min(0.1, remaining) if remaining is not None else 0.1)
            except (ValueError, OSError):
                break
            if r:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                _on_output(chunk)
                drain_after_exit = False
            elif proc.poll() is not None:
                drain_after_exit = True
                break

        if drain_after_exit:
            while True:
                try:
                    chunk = os.read(master_fd, 4096)
                    if not chunk:
                        break
                    _on_output(chunk)
                except OSError:
                    break
        proc.wait()
    finally:
        if slave_fd != -1:
            try:
                os.close(slave_fd)
            except OSError:
                pass
        os.close(master_fd)

    if proc is None or proc.returncode is None:
        raise ContainerRuntimeError(
            "PTY process never started", command=command,
        )
    return subprocess.CompletedProcess(
        args=command, returncode=proc.returncode, stdout=bytes(output_buffer), stderr=b"",
    )
