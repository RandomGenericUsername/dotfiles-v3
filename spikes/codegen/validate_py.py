#!/usr/bin/env python3
"""Python runtime enforcement for the generated contracts.

Validates fixtures against the GENERATED JSON Schemas using ``jsonschema``:
  - every line in ``fixtures/history.good.jsonl`` must validate
  - every line in ``fixtures/history.bad.jsonl`` must fail
  - every envelope in ``fixtures/events.good.json`` must validate
  - every envelope in ``fixtures/events.bad.json`` must fail

Exit 0 only when all verdicts are as expected. Run via check.sh.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
GEN = HERE / "generated"


def load(name: str) -> dict:
    return json.loads((GEN / name).read_text(encoding="utf-8"))


def validate_lines(validator: Draft202012Validator, path: Path, expected: bool) -> list[str]:
    failures: list[str] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        record = json.loads(line)
        ok = validator.is_valid(record)
        if ok != expected:
            detail = ""
            if not ok:
                err = next(iter(validator.iter_errors(record)))
                detail = f" ({'/'.join(map(str, err.absolute_path)) or '<root>'}: {err.message})"
            failures.append(f"{path.name}:{i} expected={'valid' if expected else 'invalid'} got={'valid' if ok else 'invalid'}{detail}")
    return failures


def validate_array(validator: Draft202012Validator, path: Path, expected: bool) -> list[str]:
    failures: list[str] = []
    for i, envelope in enumerate(json.loads(path.read_text(encoding="utf-8")), 1):
        ok = validator.is_valid(envelope)
        if ok != expected:
            detail = ""
            if not ok:
                err = next(iter(validator.iter_errors(envelope)))
                detail = f" ({'/'.join(map(str, err.absolute_path)) or '<root>'}: {err.message})"
            failures.append(f"{path.name}:{i} expected={'valid' if expected else 'invalid'} got={'valid' if ok else 'invalid'}{detail}")
    return failures


def main() -> int:
    history = Draft202012Validator(load("history.schema.json"))
    events = Draft202012Validator(load("events.schema.json"))
    failures: list[str] = []
    failures += validate_lines(history, HERE / "fixtures" / "history.good.jsonl", True)
    failures += validate_lines(history, HERE / "fixtures" / "history.bad.jsonl", False)
    failures += validate_array(events, HERE / "fixtures" / "events.good.json", True)
    failures += validate_array(events, HERE / "fixtures" / "events.bad.json", False)
    if failures:
        print(f"[python-jsonschema] FAIL ({len(failures)} unexpected verdict(s))")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("[python-jsonschema] PASS: history + events fixtures match expected verdicts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
