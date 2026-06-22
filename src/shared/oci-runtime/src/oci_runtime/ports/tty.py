from abc import ABC, abstractmethod


class TtyDetector(ABC):
    """Port: determines whether a terminal is available for TTY output.

    The TTY detection decision is an I/O concern — it queries
    the runtime environment (is stdout a TTY?). By abstracting it
    behind a port, the container manager stays free of direct
    sys.stdout references and can be tested without patching.
    """

    @abstractmethod
    def is_tty(self) -> bool: ...
