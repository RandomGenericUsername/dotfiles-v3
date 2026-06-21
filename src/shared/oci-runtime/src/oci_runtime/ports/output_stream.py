from abc import ABC, abstractmethod


class OutputStream(ABC):
    """Port: a writable byte stream.

    This is the minimal interface required by ``run_pty()``.  Production
    adapters write to ``sys.stdout.buffer``; test adapters can use
    ``io.BytesIO``.
    """

    @abstractmethod
    def write(self, data: bytes) -> int: ...

    @abstractmethod
    def flush(self) -> None: ...
