#!/usr/bin/env python3
"""Python-side parser for a D-Bus introspection XML contract.

Primary parser: dbus-fast's `Node.parse` (a real D-Bus introspection parser that
also validates interface/member names). If dbus-fast is unavailable we fall back
to stdlib `xml.etree` with manual D-Bus signature normalization; the CLI prints
which parser ran so the conformance harness can record it.

Output: a canonical normalized model (stable key order, 2-space indent) shaped as

    {
      "interface": "<name>",
      "methods":   [{"name": str,
                     "in":  [{"name": str, "type": str}, ...],
                     "out": [{"name": str, "type": str}, ...]}, ...],
      "signals":   [{"name": str,
                     "args": [{"name": str, "type": str}, ...]}, ...]
    }

Methods and signals are sorted by name so the ordering is a pure function of the
member set; argument order is preserved because D-Bus positions are significant.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DBUS_FAST = False
try:  # pragma: no cover - exercised by the environment, not unit tests
    from dbus_fast import introspection as _dbus_fast_introspection

    DBUS_FAST = True
except Exception:  # noqa: BLE001 - any import failure means fall back
    _dbus_fast_introspection = None


def _normalize_type(sig: object) -> str:
    """Collapse incidental whitespace so `a{sv}` == `a{ sv }`.

    dbus-fast exposes the full signature on `SignatureType.signature` (its
    `__str__` is the default repr, so `str()` is NOT usable).
    """
    if hasattr(sig, "signature"):
        sig = sig.signature  # type: ignore[attr-defined]
    return "".join(str(sig).split())


def _parse_with_dbus_fast(xml_text: str) -> dict:
    node = _dbus_fast_introspection.Node.parse(xml_text)
    interfaces = list(node.interfaces)
    if len(interfaces) != 1:
        raise ValueError(f"expected exactly 1 interface, found {len(interfaces)}")
    iface = interfaces[0]

    def arg(a) -> dict:
        return {"name": a.name, "type": _normalize_type(a.type)}

    methods = []
    for m in iface.methods:
        methods.append(
            {
                "name": m.name,
                "in": [arg(a) for a in m.in_args],
                "out": [arg(a) for a in m.out_args],
            }
        )
    signals = [
        {"name": s.name, "args": [arg(a) for a in s.args]}
        for s in iface.signals
    ]
    return _canonicalize(iface.name, methods, signals)


def _parse_with_etree(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    iface_el = root.find("interface")
    if iface_el is None:
        raise ValueError("no <interface> element found")
    iface_name = iface_el.get("name", "")

    methods = []
    for m in iface_el.findall("method"):
        args = m.findall("arg")
        methods.append(
            {
                "name": m.get("name", ""),
                "in": [
                    {"name": a.get("name", ""), "type": _normalize_type(a.get("type", ""))}
                    for a in args
                    if a.get("direction", "in") == "in"
                ],
                "out": [
                    {"name": a.get("name", ""), "type": _normalize_type(a.get("type", ""))}
                    for a in args
                    if a.get("direction") == "out"
                ],
            }
        )
    signals = []
    for s in iface_el.findall("signal"):
        signals.append(
            {
                "name": s.get("name", ""),
                "args": [
                    {"name": a.get("name", ""), "type": _normalize_type(a.get("type", ""))}
                    for a in s.findall("arg")
                ],
            }
        )
    return _canonicalize(iface_name, methods, signals)


def _canonicalize(iface_name: str, methods: list[dict], signals: list[dict]) -> dict:
    methods.sort(key=lambda m: m["name"])
    signals.sort(key=lambda s: s["name"])
    # Argument order is significant in D-Bus; never reorder args, only members.
    return {"interface": iface_name, "methods": methods, "signals": signals}


def parse(path: str | Path, parser: str = "auto") -> tuple[dict, str]:
    xml_text = Path(path).read_text(encoding="utf-8")
    if parser in ("auto", "dbus-fast") and DBUS_FAST:
        return _parse_with_dbus_fast(xml_text), "dbus-fast"
    if parser == "dbus-fast" and not DBUS_FAST:
        raise RuntimeError("dbus-fast requested but not importable")
    return _parse_with_etree(xml_text), "xml.etree"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("xml", help="path to introspection XML")
    ap.add_argument("--parser", choices=["auto", "dbus-fast", "etree"], default="auto")
    ap.add_argument("--out", help="write JSON here instead of stdout")
    args = ap.parse_args()
    model, used = parse(args.xml, args.parser)
    text = json.dumps(model, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out} (parser={used})", file=sys.stderr)
    else:
        sys.stderr.write(f"# parser={used}\n")
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
