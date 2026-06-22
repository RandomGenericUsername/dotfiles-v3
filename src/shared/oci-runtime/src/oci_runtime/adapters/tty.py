import sys

from oci_runtime.ports.tty import TtyDetector


class StdoutTtyDetector(TtyDetector):
    """Adapter: detects TTY availability from sys.stdout.

    Production implementation that queries the process's stdout
    to determine if it's connected to a terminal.
    """

    def is_tty(self) -> bool:
        return sys.stdout.isatty()
