#!/usr/bin/env python3
"""Runtime-parity probe: schema verdict vs the REAL hand-written runtime.

This is the decisive check. It imports the shipped runtime (``src/runtime/src``)
and runs the exact same fixture corpus through the code that actually reads
these files, then compares the runtime's accept/reject verdict to the JSON
Schema's verdict. Any difference is a place where the neutral schema is NOT
(yet) the source of truth.

  --kind history  → InspectHistoryUseCase._parse_record  (inspect.py)
  --kind current  → JsonStateRepository._dict_to_state   (json_state_repository.py)

Exits non-zero if the two disagree on any case.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "runtime" / "src"))

from runtime.adapters.json_state_repository import JsonStateRepository  # noqa: E402
from runtime.application.inspect import InspectHistoryUseCase  # noqa: E402


def _runtime_verdict(kind: str, line: object) -> tuple[bool, str]:
    try:
        if kind == "history":
            InspectHistoryUseCase._parse_record(line, 1)
        elif kind == "current":
            repo = JsonStateRepository(state_root=Path(tempfile.mkdtemp(prefix="parity-")))
            repo._dict_to_state(line)  # noqa: SLF001 — probing the shipped parser
        else:  # pragma: no cover - argparse constrains this
            raise SystemExit(f"unknown --kind {kind!r}")
        return True, ""
    except ValueError as exc:
        return False, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["history", "current"], required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    corpus = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    divergences: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []

    for case in corpus["cases"]:
        cid = case["id"]
        runtime_valid, runtime_detail = _runtime_verdict(args.kind, case["line"])
        # `expected` in the corpus is the JSON Schema's answer (both maintained
        # validators already proved they agree with it). Compare runtime to it.
        schema_valid = bool(case["expected"])
        agree = runtime_valid == schema_valid
        rows.append(
            {
                "id": cid,
                "schema_valid": schema_valid,
                "runtime_valid": runtime_valid,
                "agree": agree,
                "runtime_detail": runtime_detail,
            }
        )
        mark = "AGREE " if agree else "DIVERGE"
        print(
            f"[runtime-parity:{args.kind}] {mark} {cid:28} "
            f"schema={schema_valid!s:5} runtime={runtime_valid!s:5}"
            + (f"  runtime says: {runtime_detail}" if not agree and runtime_detail else "")
        )
        if not agree:
            divergences.append(rows[-1])

    out = {
        "validator": f"python-runtime-parser:{args.kind}",
        "cases": args.cases,
        "rows": rows,
        "divergences": divergences,
    }
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if divergences:
        print(
            f"[runtime-parity:{args.kind}] {len(divergences)} divergence(s) between neutral "
            f"schema and shipped parser"
        )
        return 1
    print(f"[runtime-parity:{args.kind}] shipped parser agrees with the neutral schema")
    return 0


if __name__ == "__main__":
    sys.exit(main())
