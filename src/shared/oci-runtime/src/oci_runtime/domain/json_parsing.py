import json

from oci_runtime.domain.exceptions import ParsingError


def parse_json_item(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ParsingError(raw=raw, message=f"Invalid JSON: {e}") from e
    if not isinstance(data, (dict, list)):
        raise ParsingError(
            raw=raw,
            message=f"Expected object or array, got {type(data).__name__}",
        )
    if isinstance(data, list):
        if len(data) != 1:
            raise ParsingError(
                raw=raw,
                message=f"Expected single-item array, got {len(data)} items",
            )
        item = data[0]
        if not isinstance(item, dict):
            raise ParsingError(
                raw=raw,
                message=f"Expected dict inside array, got {type(item).__name__}",
            )
        return item
    return data


def parse_json_list(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        pass
    else:
        if isinstance(data, list):
            if not all(isinstance(item, dict) for item in data):
                raise ParsingError(
                    raw=raw,
                    message="Expected list of dicts",
                )
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
            item = json.loads(line)
        except json.JSONDecodeError:
            raise ParsingError(
                raw=raw,
                message=f"Invalid JSON on line {i}: {line[:200]}",
            )
        if not isinstance(item, dict):
            raise ParsingError(
                raw=raw,
                message=f"Expected dict on line {i}, got {type(item).__name__}",
            )
        items.append(item)
    if items:
        return items
    return []
