import shutil
import subprocess
import threading
from typing import Callable

from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.ports.transport import ExecResult, Transport


class CliTransport(Transport):
    def __init__(self, binary: str):
        self.binary = binary

    def _ensure_binary(self) -> None:
        if shutil.which(self.binary) is None:
            raise RuntimeNotAvailableError(self.binary)

    def _read_stream(
        self,
        process: subprocess.Popen,
        on_output: Callable[[bytes, str], None] | None = None,
    ) -> tuple[list[bytes], list[bytes]]:
        """Read stdout/stderr via selector until both pipes EOF."""
        stdout_acc: list[bytes] = []
        stderr_acc: list[bytes] = []
        import selectors
        selector = selectors.DefaultSelector()
        try:
            selector.register(process.stdout, selectors.EVENT_READ)
            selector.register(process.stderr, selectors.EVENT_READ)
            while True:
                if process.poll() is not None and not selector.get_map():
                    break
                if not selector.get_map():
                    process.wait(timeout=0.1)
                    continue
                events = selector.select(timeout=0.1)
                for key, _ in events:
                    data = key.fileobj.read(1024)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    if key.fileobj is process.stdout:
                        stdout_acc.append(data)
                        if on_output:
                            on_output(data, "stdout")
                    else:
                        stderr_acc.append(data)
                        if on_output:
                            on_output(data, "stderr")
        finally:
            selector.close()
        return stdout_acc, stderr_acc

    def execute(
        self,
        command: list[str],
        *,
        timeout: int | None = None,
        input_data: bytes | None = None,
        stream: bool = False,
        on_output: Callable[[bytes, str], None] | None = None,
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

            stdout_acc, stderr_acc = self._read_stream(process, on_output)

            if _stdin_thread:
                _stdin_thread.join(timeout=5)

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
