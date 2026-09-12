#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["dbus-fast"]
# ///
"""Executable conformance check for a single-source-of-truth D-Bus contract.

Parses ONE introspection XML with two independent D-Bus parsers and asserts they
produce the same normalized model, then asserts that model matches the hand-kept
machine contract in contracts/event-contract.json. Finally it can assert that a
signal a producer claims to emit is actually declared in the XML.

    uv run spikes/dbus-xml/conformance.py
    uv run spikes/dbus-xml/conformance.py --check-emitted JobCrashed   # fails

Exit codes: 0 = conformant, 1 = conformance failure, 2 = usage/IO error.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
DEFAULT_XML = HERE / "org.dotfiles.Events1.xml"
DEFAULT_CONTRACT = REPO_ROOT / "contracts" / "event-contract.json"
GJS_PARSER = HERE / "gjs_parse.js"

sys.path.insert(0, str(HERE))
import python_parse  # noqa: E402


def flat(model: dict) -> dict:
    """Canonical comparable form: name -> signature strings, order-preserving."""
    return {
        "interface": model["interface"],
        "methods": {
            m["name"]: {
                "in": [f"{a['name']}:{a['type']}" for a in m["in"]],
                "out": [f"{a['name']}:{a['type']}" for a in m["out"]],
            }
            for m in model["methods"]
        },
        "signals": {
            s["name"]: [f"{a['name']}:{a['type']}" for a in s["args"]]
            for s in model["signals"]
        },
    }


def contract_flat(contract: dict) -> dict:
    return {
        "interface": contract["interface"],
        "methods": {
            name: {"in": spec.get("in", []), "out": spec.get("out", [])}
            for name, spec in contract["methods"].items()
        },
        "signals": {name: list(args) for name, args in contract["signals"].items()},
    }


def parse_gjs(xml_path: Path) -> dict:
    gjs = shutil.which("gjs")
    if gjs is None:
        raise RuntimeError("gjs not found on PATH")
    proc = subprocess.run(
        [gjs, str(GJS_PARSER), str(xml_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"gjs parser exited {proc.returncode}\n--- stderr ---\n{proc.stderr}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover
        raise RuntimeError(f"gjs parser emitted non-JSON: {exc}\n{proc.stdout}") from exc


def diff_flat(a: dict, b: dict, a_name: str, b_name: str) -> list[str]:
    problems: list[str] = []
    if a["interface"] != b["interface"]:
        problems.append(f"interface: {a_name}={a['interface']!r} vs {b_name}={b['interface']!r}")
    for section in ("methods", "signals"):
        a_keys, b_keys = set(a[section]), set(b[section])
        for name in sorted(a_keys - b_keys):
            problems.append(f"{section}: {name!r} present in {a_name} but missing from {b_name}")
        for name in sorted(b_keys - a_keys):
            problems.append(f"{section}: {name!r} present in {b_name} but missing from {a_name}")
        for name in sorted(a_keys & b_keys):
            if a[section][name] != b[section][name]:
                problems.append(
                    f"{section}.{name}: {a_name}={a[section][name]!r} vs "
                    f"{b_name}={b[section][name]!r}"
                )
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xml", type=Path, default=DEFAULT_XML)
    ap.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    ap.add_argument(
        "--check-emitted",
        metavar="SIGNAL",
        help="assert SIGNAL is declared in the XML; simulates a producer emitting an undeclared signal",
    )
    ap.add_argument("--no-contract", action="store_true", help="skip XML<->JSON contract check")
    args = ap.parse_args()

    if not args.xml.exists():
        print(f"error: XML not found: {args.xml}", file=sys.stderr)
        return 2
    if not args.contract.exists() and not args.no_contract:
        print(f"error: contract not found: {args.contract}", file=sys.stderr)
        return 2

    py_model, py_parser = python_parse.parse(args.xml)
    gjs_model = parse_gjs(args.xml)
    py_flat, gjs_flat = flat(py_model), flat(gjs_model)

    print(f"[1/4] Python parser : {py_parser} -> "
          f"{len(py_flat['methods'])} methods, {len(py_flat['signals'])} signals")
    print(f"[2/4] GJS parser    : Gio.DBusNodeInfo.new_for_xml -> "
          f"{len(gjs_flat['methods'])} methods, {len(gjs_flat['signals'])} signals")

    problems = diff_flat(py_flat, gjs_flat, "python", "gjs")
    if problems:
        print("[3/4] cross-parser agreement: FAIL")
        for p in problems:
            print(f"      - {p}")
    else:
        print("[3/4] cross-parser agreement: PASS "
              "(interface, methods in/out, signals args identical)")

    contract_problems: list[str] = []
    if not args.no_contract:
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        contract_problems = diff_flat(py_flat, contract_flat(contract), "xml", "contract")
        if contract_problems:
            print(f"[4/4] XML <-> {args.contract.name}: FAIL")
            for p in contract_problems:
                print(f"      - {p}")
        else:
            print(f"[4/4] XML <-> {args.contract.name}: PASS "
                  "(interface, methods in/out, signals args identical)")
    else:
        print("[4/4] XML <-> contract: SKIPPED")

    emitted_problem: list[str] = []
    if args.check_emitted:
        known = set(py_flat["signals"])
        if args.check_emitted not in known:
            emitted_problem.append(
                f"signal {args.check_emitted!r} is emitted but not declared in XML; "
                f"declared signals: {sorted(known)}"
            )
        else:
            print(f"[emit ] declared-signal guard: PASS ({args.check_emitted!r} in XML)")

    failed = bool(problems or contract_problems or emitted_problem)
    if emitted_problem:
        for p in emitted_problem:
            print(f"[emit ] declared-signal guard: FAIL\n      - {p}")

    print("RESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
