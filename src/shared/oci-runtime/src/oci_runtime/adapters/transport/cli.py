import shutil
import subprocess
import threading
from typing import Callable

from oci_runtime.adapters._process_reader import ProcessPipeReader
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.domain.types import CancellationToken, ExecResult
from oci_runtime.ports.transport import Transport


class CliTransport(Transport):
    def __init__(self, binary: str):
        self.binary = binary

    def _ensure_binary(self) -> None:
        if shutil.which(self.binary) is None:
            raise RuntimeNotAvailableError(self.binary)

    def execute(
        self,
        command: list[str],
        *,
        timeout: int | None = None,
        input_data: bytes | None = None,
        stream: bool = False,
        on_output: Callable[[bytes, str], None] | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> ExecResult:
        self._ensure_binary()

        # If no streaming is requested, use the simpler subprocess.run
        if not on_output and not stream:
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    timeout=timeout,
                    input=input_data,
                )
                return ExecResult(
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
            except FileNotFoundError:
                raise RuntimeNotAvailableError(self.binary) from None
            except subprocess.TimeoutExpired:
                raise

        # Streaming implementation using Popen
        # Single outer try/finally guarantees child is always reaped.
        process: subprocess.Popen | None = None
        _stdin_thread: threading.Thread | None = None
        _process_reaped = False
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE if input_data else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )

            # Fix 16b: Write stdin in a daemon thread to prevent deadlock.
            if input_data:
                def _write_stdin() -> None:
                    process.stdin.write(input_data)
                    process.stdin.close()
                _stdin_thread = threading.Thread(target=_write_stdin, daemon=True)
                _stdin_thread.start()

            reader = ProcessPipeReader(process)
            stdout_acc, stderr_acc = reader.read(on_output, cancel_token)

            if _stdin_thread:
                _stdin_thread.join(timeout=5)

            if cancel_token and cancel_token.is_cancelled:
                process.kill()
                process.wait()
                _process_reaped = True
                return ExecResult(
                    returncode=-1,
                    stdout=b"".join(stdout_acc),
                    stderr=b"".join(stderr_acc),
                )

            returncode = process.wait(timeout=timeout)
            _process_reaped = True
            return ExecResult(
                returncode=returncode,
                stdout=b"".join(stdout_acc),
                stderr=b"".join(stderr_acc),
            )

        except FileNotFoundError:
            raise RuntimeNotAvailableError(self.binary) from None
        except subprocess.TimeoutExpired:
            if process and process.poll() is None:
                process.kill()
                process.wait()
            _process_reaped = True
            raise
        finally:
            # Guaranteed: child is always reaped regardless of exception path
            if process and not _process_reaped:
                process.kill()
                process.wait()
            if process:
                for pipe in (process.stdout, process.stderr, process.stdin):
                    if pipe:
                        pipe.close()

    def probe(self) -> bool:
        try:
            result = subprocess.run(
                [self.binary, "--version"],
                capture_output=True,
                timeout=30,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def get_runtime_binary(self) -> str:
        """Get the runtime binary path/name."""
        self._ensure_binary()
        return self.binary