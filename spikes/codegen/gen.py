#!/usr/bin/env python3
"""Single-source code generator for the runtime<->shell contracts.

Reads ``contract.json`` (the single source) and emits, deterministically and
byte-for-byte reproducibly:

  generated/history.schema.json   JSON Schema (draft 2020-12) for a history line
  generated/events.schema.json    JSON Schema for the event wire envelopes
  generated/contract.py           Python constants + dataclasses/TypedDicts
  generated/contract.ts           TypeScript types + constants

Determinism: JSON is written with sorted keys and a trailing newline; code is
emitted from ordered source structures. ``check.sh`` regenerates and runs
``git diff --exit-code`` over ``generated/`` so any drift fails by execution.

Run: ``python3 gen.py`` (stdlib only).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

def screaming(name: str) -> str:
    """HistoryTrigger -> HISTORY_TRIGGER."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "contract.json"
OUT = HERE / "generated"

# ---- type system -----------------------------------------------------------
# History-side DSL scalars. ``dbus`` is informational: the history line is JSON.
DSL_TYPES: dict[str, dict[str, Any]] = {
    "string": {"json": {"type": "string"}, "py": "str", "ts": "string", "dbus": "s"},
    "timestamp": {
        "json": {"type": "string", "format": "date-time"},
        "py": "str",
        "ts": "string",
        "dbus": "s",
    },
    "sha256": {
        "json": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "py": "str",
        "ts": "Sha256",
        "dbus": "s",
    },
    "uint": {"json": {"type": "integer", "minimum": 0}, "py": "int", "ts": "number", "dbus": "u"},
    "uint_map": {
        "json": {"type": "object", "additionalProperties": {"type": "integer", "minimum": 0}},
        "py": "dict[str, int]",
        "ts": "Record<string, number>",
        "dbus": "a{su}",
    },
    "string_list": {
        "json": {"type": "array", "items": {"type": "string"}},
        "py": "list[str]",
        "ts": "string[]",
        "dbus": "as",
    },
}

# D-Bus signature -> cross-language outputs. Only a subset of the D-Bus type
# system is covered; see reviews/schema-codegen.md for the gaps.
DBUS_TYPES: dict[str, dict[str, Any]] = {
    "s": {"json": {"type": "string"}, "py": "str", "ts": "string"},
    "u": {"json": {"type": "integer", "minimum": 0}, "py": "int", "ts": "number"},
    "i": {"json": {"type": "integer"}, "py": "int", "ts": "number"},
    "x": {"json": {"type": "integer"}, "py": "int", "ts": "number"},
    "d": {"json": {"type": "number"}, "py": "float", "ts": "number"},
    "b": {"json": {"type": "boolean"}, "py": "bool", "ts": "boolean"},
    "a{sv}": {"json": {"type": "object"}, "py": "dict[str, object]", "ts": "Record<string, unknown>"},
    "a{ss}": {
        "json": {"type": "object", "additionalProperties": {"type": "string"}},
        "py": "dict[str, str]",
        "ts": "Record<string, string>",
    },
    "as": {"json": {"type": "array", "items": {"type": "string"}}, "py": "list[str]", "ts": "string[]"},
    "v": {"json": {}, "py": "object", "ts": "unknown"},
}


def nullable(type_name: str) -> tuple[str, bool]:
    if type_name.endswith("?"):
        return type_name[:-1], True
    return type_name, False


def _py(type_name: str, enums: dict[str, list[str]]) -> str:
    base, opt = nullable(type_name)
    if base == "HistoryDetails":
        inner = "HistoryDetails"
    elif base in enums:
        inner = base
    else:
        inner = DSL_TYPES[base]["py"]
    return f"{inner} | None" if opt else inner


def _ts(type_name: str, enums: dict[str, list[str]]) -> str:
    base, opt = nullable(type_name)
    if base == "HistoryDetails":
        inner = "HistoryDetails"
    elif base in enums:
        inner = base
    else:
        inner = DSL_TYPES[base]["ts"]
    return f"{inner} | null" if opt else inner


def _json_scalar(type_name: str) -> dict[str, Any]:
    base, opt = nullable(type_name)
    schema = json.loads(json.dumps(DSL_TYPES[base]["json"]))
    if opt:
        schema = {"anyOf": [schema, {"type": "null"}]}
    return schema


def _dbus_py(sig: str) -> str:
    return DBUS_TYPES[sig]["py"]


def _dbus_ts(sig: str) -> str:
    return DBUS_TYPES[sig]["ts"]


def _dbus_json(sig: str) -> dict[str, Any]:
    return json.loads(json.dumps(DBUS_TYPES[sig]["json"]))


# ---- history schema --------------------------------------------------------
def build_history_schema(src: dict[str, Any]) -> dict[str, Any]:
    enums = src["enums"]
    hist = src["history"]
    defs: dict[str, Any] = {
        "Sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "HistoryTrigger": {"enum": enums["HistoryTrigger"]},
    }

    detail_defs: dict[str, Any] = {}
    detail_names: list[str] = []
    for trigger, fields in hist["details"].items():
        required = [k for k in fields if not k.endswith("?")]
        props = {k.rstrip("?"): _json_scalar(fields[k]) for k in fields}
        name = f"Details_{trigger}"
        detail_names.append(name)
        detail_defs[name] = {
            "type": "object",
            "additionalProperties": False,
            "required": required,
            "properties": props,
        }
    defs.update(detail_defs)
    defs["HistoryDetails"] = {"oneOf": [{"$ref": f"#/$defs/{n}"} for n in detail_names]}

    props = {}
    required = []
    for field in hist["fields"]:
        name, type_name = field["name"], field["type"]
        base, opt = nullable(type_name)
        if base == "HistoryDetails":
            props[name] = {"$ref": "#/$defs/HistoryDetails"}
        elif base in enums:
            props[name] = {"$ref": f"#/$defs/{base}"}
        else:
            props[name] = _json_scalar(type_name)
        if field["required"]:
            required.append(name)

    # Per-trigger details guard: triggers with a declared shape must (when
    # details is present) match it; triggers without one must not carry details.
    clauses: list[dict[str, Any]] = []
    all_triggers = set(enums["HistoryTrigger"])
    shaped = set(hist["details"])
    for trigger in sorted(shaped):
        clauses.append(
            {
                "if": {"properties": {"trigger": {"const": trigger}}, "required": ["trigger"]},
                "then": {"properties": {"details": {"$ref": f"#/$defs/Details_{trigger}"}}},
            }
        )
    unshaped = sorted(all_triggers - shaped)
    if unshaped:
        clauses.append(
            {
                "if": {"properties": {"trigger": {"enum": unshaped}}, "required": ["trigger"]},
                "then": {"properties": {"details": False}},
            }
        )

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://dotfiles.local/generated/history.schema.json",
        "$defs": defs,
        "title": hist["title"],
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": props,
        "allOf": clauses,
    }


# ---- event schema ----------------------------------------------------------
def _members_schema(members: dict[str, str], enums: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(members),
        "properties": {k: _dbus_json(v) for k, v in members.items()},
    }


def build_events_schema(src: dict[str, Any]) -> dict[str, Any]:
    ev = src["events"]
    defs: dict[str, Any] = {}

    for name, sig in ev["signals"].items():
        defs[f"Signal_{name}"] = _members_schema(sig, src["enums"])
    for name, spec in ev["methods"].items():
        defs[f"MethodIn_{name}"] = _members_schema(spec["in"], src["enums"])
        defs[f"MethodOut_{name}"] = _members_schema(spec["out"], src["enums"])
    for topic, spec in ev["topics"].items():
        payload = dict(spec["payload"])
        schema = _members_schema(payload, src["enums"])
        for key, allowed in spec.get("enum", {}).items():
            schema["properties"][key]["enum"] = allowed
        defs[f"Topic_{topic.replace('.', '_')}"] = schema

    signal_env = {
        "type": "object",
        "additionalProperties": False,
        "required": ["signal", "members"],
        "properties": {
            "signal": {"enum": sorted(ev["signals"])},
            "members": {"type": "object"},
        },
        "allOf": [
            {
                "if": {"properties": {"signal": {"const": n}}, "required": ["signal"]},
                "then": {"properties": {"members": {"$ref": f"#/$defs/Signal_{n}"}}},
            }
            for n in sorted(ev["signals"])
        ],
    }
    method_env = {
        "type": "object",
        "additionalProperties": False,
        "required": ["method", "args"],
        "properties": {
            "method": {"enum": sorted(ev["methods"])},
            "args": {"type": "object"},
        },
        "allOf": [
            {
                "if": {"properties": {"method": {"const": n}}, "required": ["method"]},
                "then": {"properties": {"args": {"$ref": f"#/$defs/MethodIn_{n}"}}},
            }
            for n in sorted(ev["methods"])
        ],
    }
    topic_env = {
        "type": "object",
        "additionalProperties": False,
        "required": ["topic", "producer", "payload"],
        "properties": {
            "topic": {"enum": sorted(ev["topics"])},
            "producer": {"type": "string"},
            "payload": {"type": "object"},
        },
        "allOf": [
            {
                "if": {"properties": {"topic": {"const": t}}, "required": ["topic"]},
                "then": {"properties": {"payload": {"$ref": f"#/$defs/Topic_{t.replace('.', '_')}"}}},
            }
            for t in sorted(ev["topics"])
        ],
    }
    defs["SignalEnvelope"] = signal_env
    defs["MethodEnvelope"] = method_env
    defs["TopicEnvelope"] = topic_env

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://dotfiles.local/generated/events.schema.json",
        "$defs": defs,
        "oneOf": [
            {"$ref": "#/$defs/SignalEnvelope"},
            {"$ref": "#/$defs/MethodEnvelope"},
            {"$ref": "#/$defs/TopicEnvelope"},
        ],
    }


# ---- Python emission -------------------------------------------------------
def emit_python(src: dict[str, Any]) -> str:
    enums = src["enums"]
    hist = src["history"]
    ev = src["events"]
    out: list[str] = [
        '"""GENERATED by spikes/codegen/gen.py from contract.json. DO NOT EDIT."""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass, field",
        "from typing import Final, Literal, NotRequired, TypedDict, Union",
        "",
        "",
    ]
    for name, values in enums.items():
        literal = ", ".join(f'"{v}"' for v in values)
        out.append(f"{name} = Literal[{literal}]")
        out.append(f"{screaming(name)}S: Final[tuple[str, ...]] = ({literal},)")
        out.append("")
    out.append("")

    for trigger, fields in hist["details"].items():
        cls = trigger.capitalize() + "Details"
        out.append(f"class {cls}(TypedDict):")
        for key, type_name in fields.items():
            optional = key.endswith("?")
            key_name = key.rstrip("?")
            py = _py(type_name, enums)
            if optional:
                out.append(f"    {key_name}: NotRequired[{py}]")
            else:
                out.append(f"    {key_name}: {py}")
        out.append("")
    out.append("HistoryDetails = Union[" + ", ".join(
        trigger.capitalize() + "Details" for trigger in hist["details"]
    ) + "]")
    out.append("")
    out.append("")

    out.append("@dataclass(frozen=True, slots=True)")
    out.append(f"class {hist['title']}:")
    for f in hist["fields"]:
        py = _py(f["type"], enums)
        if f["required"]:
            out.append(f"    {f['name']}: {py}")
        else:
            out.append(f"    {f['name']}: {py} = None")
    out.append("")
    out.append("")

    out.append(f"EVENTS_BUS_NAME: Final[str] = {ev['bus_name']!r}")
    out.append(f"EVENTS_OBJECT_PATH: Final[str] = {ev['object_path']!r}")
    out.append(f"EVENTS_INTERFACE: Final[str] = {ev['interface']!r}")
    out.append(f"EVENTS_ERRORS: Final[tuple[str, ...]] = ({', '.join(repr(e) for e in ev['errors'])},)")
    out.append("")
    out.append("")
    out.append("@dataclass(frozen=True, slots=True)")
    out.append("class Member:")
    out.append("    name: str")
    out.append("    dbus: str")
    out.append("    py: str")
    out.append("")
    out.append("")
    out.append("@dataclass(frozen=True, slots=True)")
    out.append("class Method:")
    out.append("    name: str")
    out.append("    in_args: tuple[Member, ...] = field(default_factory=tuple)")
    out.append("    out_args: tuple[Member, ...] = field(default_factory=tuple)")
    out.append("")
    out.append("")

    def members_tuple(members: dict[str, str]) -> str:
        if not members:
            return "()"
        inner = ", ".join(f"Member({k!r}, {sig!r}, {_dbus_py(sig)!r})" for k, sig in members.items())
        return f"({inner},)"

    out.append("EVENTS_METHODS: Final[tuple[Method, ...]] = (")
    for name, spec in ev["methods"].items():
        out.append("    Method(")
        out.append(f"        {name!r},")
        out.append(f"        in_args={members_tuple(spec['in'])},")
        out.append(f"        out_args={members_tuple(spec['out'])},")
        out.append("    ),")
    out.append(")")
    out.append("")
    out.append("EVENTS_SIGNALS: Final[tuple[Method, ...]] = (")
    for name, members in ev["signals"].items():
        out.append("    Method(")
        out.append(f"        {name!r},")
        out.append(f"        out_args={members_tuple(members)},")
        out.append("    ),")
    out.append(")")
    out.append("")
    out.append("")
    for topic, spec in ev["topics"].items():
        cls = "".join(part.capitalize() for part in topic.replace(".", "_").split("_")) + "Payload"
        out.append(f"class {cls}(TypedDict):")
        for key, sig in spec["payload"].items():
            out.append(f"    {key}: {_dbus_py(sig)}")
        out.append("")
    out.append("")
    return "\n".join(out) + "\n"


# ---- TypeScript emission ---------------------------------------------------
def emit_typescript(src: dict[str, Any]) -> str:
    enums = src["enums"]
    hist = src["history"]
    ev = src["events"]
    out: list[str] = [
        "// GENERATED by spikes/codegen/gen.py from contract.json. DO NOT EDIT.",
        "",
        "/** A SHA-256 hex digest (64 lowercase hex chars). */",
        "export type Sha256 = string;",
        "",
    ]
    for name, values in enums.items():
        const = screaming(name) + "S"
        out.append(f"export const {const} = [" + ", ".join(f'"{v}"' for v in values) + "] as const;")
        out.append(f"export type {name} = (typeof {const})[number];")
        out.append("")
    out.append("")

    for trigger, fields in hist["details"].items():
        cls = trigger.capitalize() + "Details"
        out.append(f"export interface {cls} {{")
        for key, type_name in fields.items():
            optional = key.endswith("?")
            key_name = key.rstrip("?")
            out.append(f"  {key_name}{'?' if optional else ''}: {_ts(type_name, enums)};")
        out.append("}")
        out.append("")
    out.append("export type HistoryDetails = " + " | ".join(
        trigger.capitalize() + "Details" for trigger in hist["details"]
    ))
    out.append("")
    out.append("")
    out.append(f"export interface {hist['title']} {{")
    for f in hist["fields"]:
        optional = not f["required"]
        out.append(f"  {f['name']}{'?' if optional else ''}: {_ts(f['type'], enums)};")
    out.append("}")
    out.append("")
    out.append("")

    out.append(f"export const EVENTS_BUS_NAME = {json.dumps(ev['bus_name'])} as const;")
    out.append(f"export const EVENTS_OBJECT_PATH = {json.dumps(ev['object_path'])} as const;")
    out.append(f"export const EVENTS_INTERFACE = {json.dumps(ev['interface'])} as const;")
    out.append(
        "export const EVENTS_ERRORS = ["
        + ", ".join(f'"{e}"' for e in ev["errors"])
        + "] as const;"
    )
    out.append("export type EventError = (typeof EVENTS_ERRORS)[number];")
    out.append("")
    out.append("export const EVENTS_METHODS = {")
    for name, spec in ev["methods"].items():
        out.append(f"  {name}: {{")
        out.append("    in: { " + ", ".join(f'{k}: "{v}"' for k, v in spec["in"].items()) + " },")
        out.append("    out: { " + ", ".join(f'{k}: "{v}"' for k, v in spec["out"].items()) + " },")
        out.append("  },")
    out.append("} as const;")
    out.append("")
    out.append("export const EVENTS_SIGNALS = {")
    for name, members in ev["signals"].items():
        out.append("  " + name + ": { " + ", ".join(f'{k}: "{v}"' for k, v in members.items()) + " },")
    out.append("} as const;")
    out.append("")
    out.append("export const EVENTS_TOPICS = {")
    for topic, spec in ev["topics"].items():
        out.append(f"  {json.dumps(topic)}: {{ producer: {json.dumps(spec['producer'])} }},")
    out.append("} as const;")
    out.append("")
    out.append("")

    for topic, spec in ev["topics"].items():
        cls = "".join(part.capitalize() for part in topic.replace(".", "_").split("_")) + "Payload"
        out.append(f"export interface {cls} {{")
        for key, sig in spec["payload"].items():
            out.append(f"  {key}: {_dbus_ts(sig)};")
        out.append("}")
        out.append("")
    return "\n".join(out) + "\n"


def main() -> None:
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    artifacts = {
        "history.schema.json": json.dumps(build_history_schema(src), indent=2, sort_keys=True) + "\n",
        "events.schema.json": json.dumps(build_events_schema(src), indent=2, sort_keys=True) + "\n",
        "contract.py": emit_python(src),
        "contract.ts": emit_typescript(src),
    }
    for name, text in artifacts.items():
        (OUT / name).write_text(text, encoding="utf-8")
        print(f"[gen] generated/{name} ({len(text)} bytes, {text.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
