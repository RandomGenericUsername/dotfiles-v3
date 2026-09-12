#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["dbus-fast"]
# ///
"""Runtime-validation demonstration on the Python hub side.

Parse the contract XML once (dbus-fast), derive each signal's D-Bus body
signature from it, then validate candidate outgoing bodies with dbus-fast's
`SignatureTree.verify` -- the same marshal-time check the library applies when a
`ServiceInterface` signal is actually sent. No code generation: the XML drives
the check at runtime.

Usage: uv run spikes/dbus-xml/python_runtime_validate.py <path-to-xml>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import python_parse  # noqa: E402
from dbus_fast.signature import SignatureTree  # noqa: E402


def main() -> int:
    xml = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "org.dotfiles.Events1.xml"
    model, parser = python_parse.parse(xml)
    print(f"parser={parser} interface={model['interface']}")

    # A signal body signature is a bare type sequence (NOT a struct).
    sig_sig = {
        s["name"]: "".join(a["type"] for a in s["args"]) for s in model["signals"]
    }

    cases = [
        ("JobStarted/ssu (declared)", "JobStarted", ["j1", "capture", 7]),
        ("JobStarted/sss (wrong types)", "JobStarted", ["j1", "capture", "x"]),
        ("JobCrashed/ssu (undeclared)", "JobCrashed", ["j1", "capture", 7]),
        ("JobsCleared/u (declared)", "JobsCleared", [9]),
    ]
    bad = 0
    for label, name, body in cases:
        sig = sig_sig.get(name)
        if sig is None:
            print(f"signal REJECT  {label:<30}  signal '{name}' not declared in XML")
            bad += 1
            continue
        try:
            SignatureTree(sig).verify(body)
        except Exception as exc:  # noqa: BLE001
            print(f"signal REJECT  {label:<30}  declared ({sig}): {type(exc).__name__}: {exc}")
            bad += 1
        else:
            print(f"signal ACCEPT  {label:<30}  declared ({sig}) == body")

    methods = {m["name"]: (m["in"], m["out"]) for m in model["methods"]}
    cin, cout = methods["Control"]
    print(f"method lookup Control -> in={[a['type'] for a in cin]} out={[a['type'] for a in cout]}")
    print(f"method lookup LaunchJob -> {'REJECT (undeclared)' if 'LaunchJob' not in methods else 'found'}")

    print(f"RESULT: {'PASS' if bad == 2 else 'FAIL'} (expected exactly 2 rejections, got {bad})")
    return 0 if bad == 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
