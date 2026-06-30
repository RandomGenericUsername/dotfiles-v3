from typing import Generic, TypeVar
from abc import ABC, abstractmethod

T = TypeVar("T")


class ListExecutor(ABC, Generic[T]):
    @abstractmethod
    def execute_list(
        self,
        subcommand: list[str],
        entity_type: str,
        *,
        show_all: bool = False,
        filters: dict[str, str] | None = None,
    ) -> list[T]: ...
