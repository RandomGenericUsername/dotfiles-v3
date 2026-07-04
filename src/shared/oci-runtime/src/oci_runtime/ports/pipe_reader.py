from abc import ABC, abstractmethod


class PipeReader(ABC):
    @abstractmethod
    def read(
        self,
        on_stdout=None,
        on_stderr=None,
        cancel_token=None,
    ): ...
