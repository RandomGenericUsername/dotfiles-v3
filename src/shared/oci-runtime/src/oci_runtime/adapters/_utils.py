import re


def parse_size_to_bytes(size_str: str) -> int:
    """Convert a human-readable size string (e.g. '1.5GB', '512MB') to bytes."""
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
    match = re.fullmatch(r"(\d*\.?\d+)\s*([a-zA-Z]+)", size_str.upper())
    if not match:
        raise ValueError(f"Cannot parse size string: {size_str!r}")
    number, unit = match.groups()
    if unit not in units:
        raise ValueError(f"Unknown size unit: {unit!r} in {size_str!r}")
    return int(float(number) * units[unit])


from oci_runtime.domain.size_parsing import *  # noqa: F401, E402, F403 — re-export shim, deleted in T4
