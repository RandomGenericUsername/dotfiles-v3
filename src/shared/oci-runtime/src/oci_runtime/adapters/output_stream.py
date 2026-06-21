import sys

from oci_runtime.ports.output_stream import OutputStream


class StdoutBufferStream(OutputStream):
    """Adapter: writes to ``sys.stdout.buffer``.

    Production implementation that sends PTY output directly to
    the process's stdout file descriptor.
    """

    def write(self, data: bytes) -> int:
        return sys.stdout.buffer.write(data)

    def flush(self) -> None:
        sys.stdout.buffer.flush()
