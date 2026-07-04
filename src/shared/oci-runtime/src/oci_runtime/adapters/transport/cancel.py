import threading

from oci_runtime.ports.cancellation import CancellationToken


class _CancelContext:
    """Context manager that signals cancellation and runs cleanup."""

    def __init__(self, cancel_token: CancellationToken | None = None):
        self._cancel_token = cancel_token
        self._event = threading.Event()

    @property
    def is_cancelled(self) -> bool:
        if self._cancel_token and self._cancel_token.is_cancelled:
            return True
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def __enter__(self) -> "_CancelContext":
        return self

    def __exit__(self, *args) -> None:
        self.cancel()
