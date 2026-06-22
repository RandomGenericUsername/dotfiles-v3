from abc import ABC, abstractmethod


class CancellationToken(ABC):
    """Port: signals cancellation across threads.

    Pure interface — concrete adapters (ThreadCancellationToken,
    DeadlineCancellationToken, CompositeCancellationToken) live in
    adapters/_cancellation.py.
    """

    @abstractmethod
    def cancel(self) -> None: ...

    @property
    @abstractmethod
    def is_cancelled(self) -> bool: ...
