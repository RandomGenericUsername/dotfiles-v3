import json
import re

from oci_runtime.adapters._utils import parse_size_to_bytes
from oci_runtime.ports.parsers import ParsingError


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
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                raise ParsingError(
                    raw=raw,
                    message=f"Invalid JSON on line {i}: {line[:200]}",
                )
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
