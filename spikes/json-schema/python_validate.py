#!/usr/bin/env python3
"""Neutral-schema validator (Python / jsonschema).

Reads a shared case corpus and validates every case against a JSON Schema
draft 2020-12 document using the maintained ``jsonschema`` library. Exits
non-zero if any case verdict disagrees with the corpus's ``expected``.

Corpus shape::

    {"schema": "<relative path hint>",
     "cases": [{"id": str, "expected": bool, "why": str, "line": <json>}, ...]}

Machine-readable verdicts are written to ``--out`` so the conformance
script can diff this validator's answers against the JS validator's.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


def _format_error(err: ValidationError) -> str:
    path = "/".join(str(p) for p in err.absolute_path) or "<root>"
    return f"{path}: {err.message}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    corpus = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    verdicts: dict[str, bool] = {}
    expected: dict[str, bool] = {}
    mismatches: list[dict[str, object]] = []

    for case in corpus["cases"]:
        cid = case["id"]
        exp = bool(case["expected"])
        errors = sorted(validator.iter_errors(case["line"]), key=lambda e: list(e.absolute_path))
        valid = not errors
        verdicts[cid] = valid
        expected[cid] = exp
        status = "PASS" if valid == exp else "EXPECTED-MISMATCH"
        detail = ""
        if errors:
            detail = "  " + " | ".join(_format_error(e) for e in errors[:3])
        print(f"[python-jsonschema] {status:18} {cid}{detail}")
        if valid != exp:
            mismatches.append(
                {"id": cid, "schema_valid": valid, "expected": exp, "why": case.get("why", "")}
            )

    out = {
        "validator": "python-jsonschema",
        "jsonschema_version": _version(),
        "schema": args.schema,
        "cases": args.cases,
        "verdicts": verdicts,
        "expected": expected,
        "mismatches": mismatches,
    }
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if mismatches:
        print(f"[python-jsonschema] {len(mismatches)} expected-verdict mismatch(es)")
        return 1
    print(f"[python-jsonschema] all {len(verdicts)} cases match expected")
    return 0


def _version() -> str:
    from importlib.metadata import version

    return version("jsonschema")


if __name__ == "__main__":
    sys.exit(main())
