import re


def parse_size_to_bytes(size_str: str) -> int:
    """Helper to convert strings like '1.24GB' or '512MB' to bytes."""
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
        return 0
    number, unit = match.groups()
    return int(float(number) * units.get(unit, 0))


class BaseCliParser:
    """Shared logic for CLI parsers."""
    def parse_prune(self, raw: str) -> dict[str, int]:
        deleted_count = 0
        reclaimed_bytes = 0

        id_pattern = re.compile(r"^[a-f0-9]{12,64}$", re.MULTILINE)
        deleted_count = len(id_pattern.findall(raw))

        space_match = re.search(r"Total reclaimed space:\s*(.*)", raw, re.IGNORECASE)
        if space_match:
            reclaimed_bytes = parse_size_to_bytes(space_match.group(1))

        return {
            "deleted": deleted_count,
            "reclaimed_bytes": reclaimed_bytes
        }
