import json
import re

from oci_runtime.ports.parsers import ParsingError


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
        raise ValueError(f"Cannot parse size string: {size_str!r}")
    number, unit = match.groups()
    return int(float(number) * units.get(unit, 0))


class BaseCliParser:
    """Shared logic for CLI parsers."""

    _not_found_patterns: tuple[str, ...] = ()

    def _parse_json_item(self, raw: str) -> dict:
        """Parse JSON that may be a list with a single item or a dict."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ParsingError(raw=raw, message=f"Invalid JSON: {e}") from e
        if not data:
            raise ParsingError(raw=raw, message="Empty response")
        return data[0] if isinstance(data, list) else data

    def _parse_json_list(self, raw: str) -> list[dict]:
        """Parse JSON that contains a list, a single object, or NDJSON."""
        try:
            data = json.loads(raw)
            if not data:
                raise ParsingError(raw=raw, message="Empty response")
            if isinstance(data, list):
                return data
            return [data]
        except json.JSONDecodeError:
            pass

        lines = raw.strip().split("\n")
        items: list[dict] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if items:
            return items
        raise ParsingError(raw=raw, message="Invalid JSON in list response")

    def is_not_found_error(self, stderr: str) -> bool:
        lower = stderr.lower()
        return any(p in lower for p in self._not_found_patterns)

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
