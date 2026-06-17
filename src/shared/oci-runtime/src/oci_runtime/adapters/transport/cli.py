import shutil
import subprocess

from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.domain.types import ExecResult
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
    ) -> ExecResult:
        self._ensure_binary()

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
        self._ensure_binary()
        return self.binary