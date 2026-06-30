import re

from oci_runtime.domain.size_parsing import parse_size_to_bytes
from oci_runtime.domain.types import PruneResult


def parse_prune_result(raw: str) -> PruneResult:
    id_pattern = re.compile(
        r"^(?:deleted:\s*)?(?:sha256:)?([a-f0-9]{12,64})$", re.MULTILINE
    )
    deleted_count = len(id_pattern.findall(raw))

    space_match = re.search(r"Total reclaimed space:\s*(.*)", raw, re.IGNORECASE)
    reclaimed_bytes = 0
    if space_match:
        try:
            reclaimed_bytes = parse_size_to_bytes(space_match.group(1))
        except ValueError:
            reclaimed_bytes = 0

    return PruneResult(deleted=deleted_count, reclaimed_bytes=reclaimed_bytes)
