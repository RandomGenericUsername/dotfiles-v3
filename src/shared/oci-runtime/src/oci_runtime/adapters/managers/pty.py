import os
import pty
import select
import shutil
import subprocess
import sys
from collections.abc import Callable

from oci_runtime.domain.exceptions import ContainerRuntimeError, RuntimeNotAvailableError


def _default_pty_output(data: bytes) -> None:
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def run_pty(
    command: list[str],
    on_output: Callable[[bytes], None] | None = None,
) -> subprocess.CompletedProcess:
    if not command:
        raise ContainerRuntimeError("Empty command list", command=command)
    runtime = command[0]
    if not shutil.which(runtime):
        raise RuntimeNotAvailableError(runtime)

    output_buffer = bytearray()

    if on_output is None:
        def _default_handler(data: bytes) -> None:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
            output_buffer.extend(data)
        on_output = _default_handler
    else:
        _orig = on_output
        def _wrapped(data: bytes) -> None:
            _orig(data)
            output_buffer.extend(data)
        on_output = _wrapped

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

        drain_after_exit = False
        while True:
            try:
                r, _, _ = select.select([master_fd], [], [], 0.1)
            except (ValueError, OSError):
                break
            if r:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                on_output(chunk)
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
                    on_output(chunk)
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
    if proc.returncode != 0:
        raise ContainerRuntimeError(
            f"PTY command failed with exit code {proc.returncode}",
            command=command,
        )
    return subprocess.CompletedProcess(
        args=command, returncode=proc.returncode, stdout=bytes(output_buffer), stderr=b"",
    )
