import math


def cli_seconds(timeout: float | None, default: int) -> str:
    if timeout is None:
        return str(default)
    return str(max(1, math.ceil(timeout)))
