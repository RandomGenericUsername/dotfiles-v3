import threading

from oci_runtime.domain.types import CancellationToken


class ThreadCancellationToken(CancellationToken):
    """Thread-safe cancellation token backed by ``threading.Event``.

    This is the production adapter for the ``CancellationToken``
    domain port.  Unlike the old concrete token in the domain layer
    (which used a plain ``bool``), this implementation guarantees
    cross-thread visibility without relying on CPython's GIL.
    """

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

    def cancel(self) -> None:
        self._timer.cancel()
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


class CompositeCancellationToken(CancellationToken):
    """Cancelled when *any* child token is cancelled.

    Useful for combining a user-provided ``cancel_token`` with
    an internal ``DeadlineCancellationToken``.
    """

    def __init__(self, *children: CancellationToken) -> None:
        self._children = children

    def cancel(self) -> None:
        for c in self._children:
            c.cancel()

    @property
    def is_cancelled(self) -> bool:
        return any(c.is_cancelled for c in self._children)
