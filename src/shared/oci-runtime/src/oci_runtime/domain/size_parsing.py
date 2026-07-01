import re

from oci_runtime.domain.exceptions import ParsingError


def parse_size_to_bytes(size_str: str) -> int:
    size_str = size_str.strip()
    units = {
        "B": 1,
        "K": 1024,
        "KB": 1024,
        "M": 1024**2,
        "MB": 1024**2,
        "G": 1024**3,
        "GB": 1024**3,
        "T": 1024**4,
        "TB": 1024**4,
        "TIB": 1024**4,
        "P": 1024**5,
        "PB": 1024**5,
        "PIB": 1024**5,
        "E": 1024**6,
        "EB": 1024**6,
        "EIB": 1024**6,
        "KIB": 1024,
        "MIB": 1024**2,
        "GIB": 1024**3,
    }
    match = re.fullmatch(r"(\d*\.?\d+)\s*([a-zA-Z]+)?", size_str.upper())
    if not match:
        raise ValueError(f"Cannot parse size string: {size_str!r}")
    number, unit = match.groups()
    if unit is not None and unit not in units:
        raise ValueError(f"Unknown size unit: {unit!r} in {size_str!r}")
    multiplier = units.get(unit, 1) if unit else 1
    return int(float(number) * multiplier)


def coerce_size(size: str | int | float | None) -> int:
    if isinstance(size, str):
        try:
            return int(size)
        except ValueError:
            try:
                return parse_size_to_bytes(size)
            except ValueError as e:
                raise ParsingError(
                    raw=str(size), message=f"Cannot parse size: {size!r}"
                ) from e
    return int(size or 0)


def safe_int(v: int | float | str | None) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
