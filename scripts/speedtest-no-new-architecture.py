#!/usr/bin/env python3
"""No-new-architecture harness for the speed-test notification path.

"Reuse the existing architecture" is otherwise unenforceable prose, so each
assertion here maps to a concrete way this change could quietly grow a new
surface:

  1. no ``org.freedesktop.Notifications.Notify`` call and no non-zero
     ``replaces_id`` in the speed-test producer or consumer path -- the
     wallpaper progress model is a BESPOKE in-place card, and a ``Notify``
     call is the most likely way to drift, because it is exactly how the
     capture tool does it and it looks perfectly reasonable;
  2. no new AGS instance name beyond the pre-existing set;
  3. no second event-bus client in the notifications app beyond the
     ``speedtest-events.ts`` sibling of ``wallpaper-events.ts``;
  4. no ``GLib.timeout_add`` polling loop in ``speedtest-events.ts`` -- the
     subscribe-before-read shape only;
  5. no new well-known D-Bus name outside the contract's ``org.dotfiles.Events``
     (plus the bus daemon and the notification daemon the app already claims).

Usage: ``python3 scripts/speedtest-no-new-architecture.py [--root REPO_ROOT]``
Exit 0 = gate green (every check it performed is printed).
Exit 1 = at least one violation; each is printed naming file and line.

Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: The pre-existing AGS instance names. A new one means a new process holding a
#: socket slot and a bus name, which is exactly the surface this change must not
#: add. ``icon-color-mapping-editor``, ``wallpaper-selector``, and
#: ``btop-theme-studio`` are one-shot on-demand tools, not autostarted
#: instances, and are listed for completeness.
ALLOWED_INSTANCE_NAMES = frozenset(
    {"ags", "capture", "notifications", "hypr-pano", "wallpaper-selector", "icon-color-mapping-editor", "btop-theme-studio"}
)

#: The speed-test producer + consumer path. The producer is in the AGS tree
#: (the panel's service); the consumer is in the notifications app.
SPEEDTEST_PRODUCER = (
    "dotfiles/config/ags/services/speedtest-service.ts",
    "dotfiles/config/ags/lib/event-bus.ts",
)
SPEEDTEST_CONSUMER = (
    "src/gui-tools/notifications/lib/speedtest-events.ts",
    "src/gui-tools/notifications/ui/NotificationsWindow.tsx",
)

#: The events client each consumer is allowed to own. wallpaper-events.ts is the
#: pre-existing one; speedtest-events.ts is the sibling this change adds. A
#: THIRD client module would be a second bus connection.
EVENT_CLIENTS = (
    "src/gui-tools/notifications/lib/wallpaper-events.ts",
    "src/gui-tools/notifications/lib/speedtest-events.ts",
)

#: Files that may claim a well-known bus name.
BUS_NAME_BEARERS = (
    "src/gui-tools/notifications/app.tsx",  # org.freedesktop.Notifications (the daemon)
    "src/gui-tools/notifications/lib/wallpaper-events.ts",  # NameOwnerChanged on org.freedesktop.DBus
    "src/gui-tools/notifications/lib/speedtest-events.ts",
    "dotfiles/config/ags/lib/event-bus.ts",
    "dotfiles/config/ags/lib/event-bus-core.ts",
)

#: Well-known names the speed-test path is allowed to touch. Anything else is a
#: new surface (a second notification protocol, a second hub, a private bus).
#: ``Events1`` is not a second name -- it is the contract's versioned INTERFACE
#: served by ``org.dotfiles.Events`` (``event-contract.json`` `interface`), so
#: it is a contract value rather than an invented one.
ALLOWED_BUS_NAMES = frozenset(
    {
        "org.dotfiles.Events",
        "org.dotfiles.Events1",
        "org.freedesktop.DBus",
        "org.freedesktop.Notifications",
    }
)

_INSTANCE_RE = re.compile(r'instanceName:\s*"([^"]+)"')
#: A D-Bus well-known name: two or more dotted segments, first segment a domain
#: label. Catches org.dotfiles.Events, org.freedesktop.DBus, com.example.Thing.
_WELL_KNOWN_RE = re.compile(
    r"\b(?:org|com|net|io|dev)\.[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+\b"
)
_NOTIFY_RE = re.compile(r"org\.freedesktop\.Notifications|\bNotify\b|\breplaces_id\b")
_REPLACES_NONZERO_RE = re.compile(r"replaces_?id\s*[:=]\s*[^0]")
_POLL_RE = re.compile(r"GLib\.timeout_add|GLib\.idle_add")
_BUS_GET_RE = re.compile(r"Gio\.bus_get_sync|Gio\.bus_get\(")


def _read(root: Path, rel: str) -> list[str] | None:
    path = root / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _scan_instance_names(root: Path, offenders: list[str]) -> int:
    checked = 0
    roots = [root / "dotfiles" / "config" / "ags", root / "src" / "gui-tools"]
    for base in roots:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("app.tsx")):
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            checked += 1
            for lineno, line in enumerate(lines, start=1):
                for name in _INSTANCE_RE.findall(line):
                    if name not in ALLOWED_INSTANCE_NAMES:
                        offenders.append(
                            f"new AGS instance name '{name}' at "
                            f"{path.relative_to(root)}:{lineno}"
                        )
    return checked


def _scan_notify(root: Path, offenders: list[str]) -> int:
    checked = 0
    for rel in SPEEDTEST_PRODUCER + SPEEDTEST_CONSUMER:
        lines = _read(root, rel)
        if lines is None:
            continue
        checked += 1
        for lineno, line in enumerate(lines, start=1):
            code = line.split("//", 1)[0]
            if not code.strip():
                continue
            if _NOTIFY_RE.search(code):
                offenders.append(
                    f"speed-test path calls the freedesktop notification protocol at "
                    f"{rel}:{lineno}: {line.strip()}"
                )
            if _REPLACES_NONZERO_RE.search(code):
                offenders.append(
                    f"speed-test path uses a non-zero replaces_id at {rel}:{lineno}: "
                    f"{line.strip()}"
                )
    return checked


def _scan_event_clients(root: Path, offenders: list[str]) -> int:
    """At most one bus connection per client module, and only the two siblings."""
    lib = root / "src" / "gui-tools" / "notifications" / "lib"
    if not lib.is_dir():
        offenders.append("MISSING notifications lib directory (event-client scan)")
        return 0
    found: list[str] = []
    for path in sorted(lib.glob("*.ts")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if _BUS_GET_RE.search(text) or "signal_subscribe" in text:
            found.append(path.name)
    checked = len(found)
    allowed = {Path(rel).name for rel in EVENT_CLIENTS}
    for name in found:
        if name not in allowed:
            offenders.append(
                f"second event-bus client in the notifications app: lib/{name} "
                f"(only {sorted(allowed)} are permitted)"
            )
    return checked


def _scan_poll(root: Path, offenders: list[str]) -> int:
    """speedtest-events.ts must subscribe-then-read, never poll."""
    rel = "src/gui-tools/notifications/lib/speedtest-events.ts"
    lines = _read(root, rel)
    if lines is None:
        # The module does not exist yet (phase 1 runs before phase 3). Nothing
        # to police; reported by the mock-parity gate's mapped-file leg instead.
        return 0
    for lineno, line in enumerate(lines, start=1):
        code = line.split("//", 1)[0]
        if _POLL_RE.search(code):
            offenders.append(
                f"polling loop in the speed-test event client at {rel}:{lineno}: "
                f"{line.strip()} (subscribe-before-read only)"
            )
    return 1


def _scan_bus_names(root: Path, offenders: list[str]) -> int:
    checked = 0
    for rel in BUS_NAME_BEARERS:
        lines = _read(root, rel)
        if lines is None:
            continue
        checked += 1
        for lineno, line in enumerate(lines, start=1):
            code = line.split("//", 1)[0]
            for name in _WELL_KNOWN_RE.findall(code):
                if name not in ALLOWED_BUS_NAMES:
                    offenders.append(
                        f"new well-known bus name '{name}' at {rel}:{lineno}"
                    )
    return checked


def main() -> int:
    ap = argparse.ArgumentParser(description="Speed-test no-new-architecture gate")
    ap.add_argument("--root", default=None, help="repo root (default: parent of scripts/)")
    args = ap.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent

    offenders: list[str] = []
    checks: list[tuple[str, int]] = [
        ("no Notify/replaces_id in the speed-test path", _scan_notify(root, offenders)),
        ("no new AGS instance name", _scan_instance_names(root, offenders)),
        ("no second event-bus client in the notifications app", _scan_event_clients(root, offenders)),
        ("no polling loop in speedtest-events.ts", _scan_poll(root, offenders)),
        ("no new well-known D-Bus name", _scan_bus_names(root, offenders)),
    ]

    for name, count in checks:
        print(f"CHECK {name} ({count} file(s) scanned)")

    if offenders:
        for offender in offenders:
            print(f"FAIL {offender}")
        print(f"speedtest-no-new-architecture: {len(offenders)} violation(s)")
        return 1

    print("speedtest-no-new-architecture: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
