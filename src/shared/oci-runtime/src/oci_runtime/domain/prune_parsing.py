import re

from oci_runtime.domain.size_parsing import parse_size_to_bytes
from oci_runtime.domain.types import PruneResult

_ID_PATTERN = re.compile(
    r"^(?:deleted:\s*)?(?:sha256:)?([a-f0-9]{12,64})$",
    re.MULTILINE | re.IGNORECASE,
)
_SPACE_PATTERN = re.compile(r"Total reclaimed space:\s*(.*)", re.IGNORECASE)


def parse_prune_result(raw: str) -> PruneResult:
    deleted_count = len(_ID_PATTERN.findall(raw))

    space_match = _SPACE_PATTERN.search(raw)
    reclaimed_bytes = 0
    if space_match:
        try:
            reclaimed_bytes = parse_size_to_bytes(space_match.group(1))
        except ValueError:
            reclaimed_bytes = 0

    return PruneResult(deleted=deleted_count, reclaimed_bytes=reclaimed_bytes)
