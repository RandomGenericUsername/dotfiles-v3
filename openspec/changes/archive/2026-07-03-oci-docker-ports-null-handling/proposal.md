## Why

`adapters/parser/docker.py:281` uses `item.get("Ports", [])` which only returns `[]` for a *missing* key. When Docker emits `"Ports": null` (observed in real CLI output for stopped containers), `.get` returns `None` and the subsequent `for p in raw_ports:` loop raises `TypeError: 'NoneType' is not iterable`. v4 B5 fixed the string-`Ports` case; explicit `null` is a separate crash path.

## What Changes

- `adapters/parser/docker.py:278`: change `item.get("Ports", [])` to `item.get("Ports") or []` so both missing-key and explicit-`None` are treated as empty.

## Capabilities

### Modified Capabilities

- `oci-docker-list-port-parsing`: `Ports` field with explicit `null` value SHALL be treated as empty (no crash, returns empty port list).

## Impact

- **Code**: one line in `adapters/parser/docker.py:278`.
- **Tests**: one new test in `tests/unit/adapters/test_docker_parser.py` feeding `{"Ports": None}`, asserting `container.ports == ()`.
- **Risk**: none — strictly tighter null-handling.