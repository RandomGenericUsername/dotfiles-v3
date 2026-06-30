from abc import ABC, abstractmethod


class CancellationToken(ABC):
    """Port: signals cancellation across threads."""

    @abstractmethod
    def cancel(self) -> None: ...

    @property
    @abstractmethod
    def is_cancelled(self) -> bool: ...


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
