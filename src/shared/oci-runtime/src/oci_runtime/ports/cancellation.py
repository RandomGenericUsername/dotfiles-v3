import threading
from abc import ABC, abstractmethod


class CancellationToken(ABC):
    """Port: signals cancellation across threads."""

    @abstractmethod
    def cancel(self) -> None: ...

    @property
    @abstractmethod
    def is_cancelled(self) -> bool: ...


class ThreadCancellationToken(CancellationToken):
    """Thread-safe cancellation token backed by ``threading.Event``."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


class DeadlineCancellationToken(CancellationToken):
    """Self-cancels after *timeout* seconds.

    The timer is started on construction.  Call ``cancel()`` to
    disarm the timer and mark as cancelled immediately.  This is
    used to enforce a total wall-clock deadline on operations.
    """

    def __init__(self, timeout: float) -> None:
        self._event = threading.Event()
        self._timer = threading.Timer(timeout, self._event.set)
        self._timer.daemon = True
        self._timer.start()

    def __del__(self) -> None:
        self._timer.cancel()

    def cancel(self) -> None:
        self._timer.cancel()
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


class CompositeCancellationToken(CancellationToken):
    """Cancelled when ANY child token is cancelled. Pure logic, no I/O."""

    def __init__(self, *children: CancellationToken) -> None:
        self._children = children

    def cancel(self) -> None:
        for c in self._children:
            c.cancel()

    @property
    def is_cancelled(self) -> bool:
        return any(c.is_cancelled for c in self._children)


def compose_tokens(
    *tokens: CancellationToken | None,
) -> CancellationToken | None:
    active = [t for t in tokens if t is not None]
    if not active:
        return None
    if len(active) == 1:
        return active[0]
    return CompositeCancellationToken(*active)
