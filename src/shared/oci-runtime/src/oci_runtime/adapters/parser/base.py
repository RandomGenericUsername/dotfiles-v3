import json
import re

from oci_runtime.adapters._utils import parse_size_to_bytes
from oci_runtime.domain.types import PruneResult
from oci_runtime.ports.parsers import ParsingError


def _coerce_size(size) -> int:
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


def _safe_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class BaseCliParser:
    """Shared logic for CLI parsers."""

    _not_found_patterns: tuple[str, ...] = ()
    _auth_error_patterns: tuple[str, ...] = ()

    def is_auth_error(self, stderr: str) -> bool:
        lower = stderr.lower()
        return any(
            re.search(rf"\b{re.escape(p)}\b", lower) for p in self._auth_error_patterns
        )

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
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
            raise ParsingError(
                raw=raw, message=f"Expected dict or list, got {type(data).__name__}"
            )

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
        return []

    def is_not_found_error(self, stderr: str) -> bool:
        lower = stderr.lower()
        return any(
            re.search(rf"\b{re.escape(p)}\b", lower) for p in self._not_found_patterns
        )

    def parse_prune(self, raw: str) -> PruneResult:
        deleted_count = 0
        reclaimed_bytes = 0

        id_pattern = re.compile(
            r"^(?:deleted:\s*)?(?:sha256:)?([a-f0-9]{12,64})$", re.MULTILINE
        )
        deleted_count = len(id_pattern.findall(raw))

        space_match = re.search(r"Total reclaimed space:\s*(.*)", raw, re.IGNORECASE)
        if space_match:
            try:
                reclaimed_bytes = parse_size_to_bytes(space_match.group(1))
            except ValueError:
                reclaimed_bytes = 0

        return PruneResult(deleted=deleted_count, reclaimed_bytes=reclaimed_bytes)
