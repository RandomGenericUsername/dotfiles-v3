## Context

One-line fix in `adapters/parser/docker.py`. No design complexity.

## Goals / Non-Goals

**Goals:** treat `"Ports": null` as empty port list.
**Non-Goals:** changing string-Ports parsing (already fixed in v4 B5), changing list-Ports parsing.

## Decisions

Use `item.get("Ports") or []` instead of `item.get("Ports", [])`. The `or` operator treats both `None` and missing-key as falsy, returning `[]` for both. Simpler than `if raw_ports is None: raw_ports = []`.

## Risks / Trade-offs

- None. The change is strictly more defensive than the current code.