import shutil
import subprocess

from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.transport import Transport


_NOT_PROBED = object()


class CliTransport(Transport):
    def __init__(self, binary: str):
        self.binary = binary
        self._which_cache: str | None | object = _NOT_PROBED

    def _ensure_binary(self) -> None:
        if self._which_cache is _NOT_PROBED:
            self._which_cache = shutil.which(self.binary)
        if self._which_cache is None:
            raise RuntimeNotAvailableError(self.binary)

    def execute(
        self,
        command: list[str],
        *,
        timeout: int | None = None,
        input_data: bytes | None = None,
    ) -> RawExecResult:
        self._ensure_binary()

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=timeout,
                input=input_data,
            )
            return RawExecResult(
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except FileNotFoundError:
            raise RuntimeNotAvailableError(self.binary) from None

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
        return self._which_cache