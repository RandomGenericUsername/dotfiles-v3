import re


def parse_size_to_bytes(size_str: str) -> int:
    """Convert a human-readable size string (e.g. '1.5GB', '512MB') to bytes."""
    units = {
        'B': 1,
        'KB': 1024,
        'MB': 1024**2,
        'GB': 1024**3,
        'TB': 1024**4,
        'KIB': 1024,
        'MIB': 1024**2,
        'GIB': 1024**3,
    }
    match = re.search(r"(\d+\.?\d*)\s*([a-zA-Z]+)", size_str.upper())
    if not match:
        raise ValueError(f"Cannot parse size string: {size_str!r}")
    number, unit = match.groups()
    if unit not in units:
        raise ValueError(f"Unknown size unit: {unit!r} in {size_str!r}")
    return int(float(number) * units[unit])
