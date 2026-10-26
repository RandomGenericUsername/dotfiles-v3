#!/usr/bin/env python3
"""Fail when an SDDM login bounces instead of starting a session.

Reads ``journalctl -u sddm`` output and reports one row per login attempt.  A
login is red when any of these is observed:

* ``Session started false`` (the greeter/session handshake timed out),
* ``Auth: sddm-helper exited with 2`` (SDDM's session-error exit),
* ``Failed to launch the display server, falling back to
  DisplayServer=x11-user`` (the greeter lost its Wayland display server), or
* a session logged out within 180 s of login without a shutdown/reboot marker.

The parser keys on the handshake and helper events, so autologin (which logs no
greeter ``Login`` line) is covered too.  Stdlib only; no journal package needed.

Usage:
    python3 scripts/check-session-bounce.py                 # current boot
    python3 scripts/check-session-bounce.py --boot -1       # previous boot
    python3 scripts/check-session-bounce.py --since today
    python3 scripts/check-session-bounce.py --json
    python3 scripts/check-session-bounce.py --self-test

Exit codes: 0 green, 1 session bounce/fallback found, 2 cannot read journal or
bad invocation.  The script never calls sudo itself.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

BOUNCE_WINDOW = timedelta(seconds=180)

ISO_TS_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))\s+"
)
SYSLOG_TS_RE = re.compile(
    r"^(?P<ts>[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
)
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
UNIT_PREFIX_RE = re.compile(r"^\S+\s+\S+\[\d+\]:\s*")
LOGIN_RE = re.compile(r"Message received from greeter: Login")
SELECTED_RE = re.compile(
    r'Session "(?P<desktop>[^"]+)" selected, command: "(?P<command>[^"]*)" for VT (?P<vt>\d+)'
)
STARTED_RE = re.compile(r"Session started (?P<ok>true|false)")
HELPER_RE = re.compile(
    r"Auth: sddm-helper exited (?:with (?P<code>\d+)|(?P<success>successfully))"
)
FALLBACK_RE = re.compile(
    r"Failed to launch the display server, falling back to DisplayServer=x11-user"
)
LOGOUT_RE = re.compile(r"Session (?P<id>\S+) logged out")
# Only explicit teardown markers suppress the early-logout verdict.  A normal
# user logout (back to the greeter) has none of these.
SHUTDOWN_RE = re.compile(
    r"Stopping Simple Desktop Display Manager"
    r"|Stopped Simple Desktop Display Manager"
    r"|Reached target (?:Shutdown|Reboot|Power-Off)"
    r"|System is (?:powering down|rebooting)"
    r"|systemd\[[0-9]+\]: (?:Shutting down|Rebooting|Powering off)"
)


@dataclass
class Event:
    ts: datetime
    kind: str
    message: str
    line_no: int
    ok: Optional[bool] = None
    code: Optional[int] = None
    vt: Optional[str] = None
    desktop: Optional[str] = None


@dataclass
class Failure:
    kind: str
    ts: datetime
    detail: str
    attempt_start: Optional[datetime] = None

    def as_json(self) -> Dict[str, object]:
        return {
            "kind": self.kind,
            "timestamp": self.ts.isoformat(),
            "detail": self.detail,
            "attempt_start": self.attempt_start.isoformat()
            if self.attempt_start
            else None,
        }


@dataclass
class Attempt:
    start: datetime
    login_ts: Optional[datetime]
    source: str
    vt: Optional[str] = None
    desktop: Optional[str] = None
    session_started: Optional[bool] = None
    started_ts: Optional[datetime] = None
    helper_events: List[Event] = field(default_factory=list)
    fallback_events: List[Event] = field(default_factory=list)
    logout_ts: Optional[datetime] = None
    shutdown_ts: Optional[datetime] = None
    failures: List[Failure] = field(default_factory=list)

    @property
    def helper_code(self) -> Optional[int]:
        for event in self.helper_events:
            if event.code == 2:
                return 2
        for event in self.helper_events:
            if event.code is not None:
                return event.code
        return None

    @property
    def end_ts(self) -> Optional[datetime]:
        for event in self.helper_events:
            if event.code == 2:
                return event.ts
        if self.logout_ts is not None:
            return self.logout_ts
        if self.started_ts is not None:
            return self.started_ts
        for event in self.helper_events:
            if event.code is not None:
                return event.ts
        return None

    @property
    def duration_seconds(self) -> Optional[int]:
        end = self.end_ts
        if end is None:
            return None
        return int((end - self.start).total_seconds())

    def as_json(self) -> Dict[str, object]:
        return {
            "login": self.login_ts.isoformat() if self.login_ts else None,
            "attempt_start": self.start.isoformat(),
            "source": self.source,
            "vt": self.vt,
            "desktop": self.desktop,
            "session_started": self.session_started,
            "helper_exit": self.helper_code,
            "duration_seconds": self.duration_seconds,
            "verdict": "FAIL" if self.failures else "PASS",
            "failures": [failure.as_json() for failure in self.failures],
        }


@dataclass
class Report:
    attempts: List[Attempt] = field(default_factory=list)
    fallbacks: List[Event] = field(default_factory=list)
    standalone_failures: List[Failure] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    # Set by the CLI; used only for JSON/presentation.
    boot: Optional[int] = None
    since: Optional[str] = None
    journal_command: Optional[List[str]] = None

    @property
    def failed_attempts(self) -> List[Attempt]:
        return [attempt for attempt in self.attempts if attempt.failures]

    @property
    def all_failures(self) -> List[Failure]:
        failures: List[Failure] = []
        for attempt in self.attempts:
            failures.extend(attempt.failures)
        failures.extend(self.standalone_failures)
        failures.sort(key=lambda failure: failure.ts)
        return failures

    @property
    def ok(self) -> bool:
        return not self.all_failures

    def as_json(self) -> Dict[str, object]:
        return {
            "ok": self.ok,
            "boot": self.boot,
            "since": self.since,
            "journal_command": self.journal_command,
            "summary": {
                "attempts": len(self.attempts),
                "failed_attempts": len(self.failed_attempts),
                "fallback_lines": len(self.fallbacks),
                "failures": len(self.all_failures),
            },
            "attempts": [attempt.as_json() for attempt in self.attempts],
            "fallbacks": [
                {
                    "timestamp": event.ts.isoformat(),
                    "line": event.message,
                    "line_no": event.line_no,
                }
                for event in self.fallbacks
            ],
            "failures": [failure.as_json() for failure in self.all_failures],
        }


def _local_tz():
    return datetime.now().astimezone().tzinfo or timezone.utc


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_local_tz())
    return dt


def _parse_timestamp(token: str, is_iso: bool) -> datetime:
    if is_iso:
        value = token[:-1] + "+00:00" if token.endswith("Z") else token
        return _aware(datetime.fromisoformat(value))
    # journalctl's short format uses locale month abbreviations; Arch/this
    # host emits lowercase "oct", so parse the month explicitly instead of
    # relying on strptime's locale handling.
    month_token, day_token, time_token = token.split()
    month = MONTHS[month_token.lower()]
    hour, minute, second = (int(part) for part in time_token.split(":"))
    now = datetime.now(_local_tz())
    parsed = datetime(
        now.year, month, int(day_token), hour, minute, second, tzinfo=_local_tz()
    )
    # journalctl short format omits the year.  A December log read in January
    # belongs to the previous year; one day of slack absorbs clock skew.
    if parsed > now + timedelta(days=1):
        parsed = parsed.replace(year=parsed.year - 1)
    return _aware(parsed)


def parse_journal(text: str) -> List[Event]:
    events: List[Event] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip("\r")
        match = ISO_TS_RE.match(line)
        is_iso = bool(match)
        if match is None:
            match = SYSLOG_TS_RE.match(line)
        if match is None:
            continue
        timestamp = _parse_timestamp(match.group("ts"), is_iso)
        rest = line[match.end() :]
        message = UNIT_PREFIX_RE.sub("", rest).strip()

        if LOGIN_RE.search(message):
            events.append(Event(timestamp, "login", message, line_no))
        elif SELECTED_RE.search(message):
            selected = SELECTED_RE.search(message)
            assert selected is not None
            events.append(
                Event(
                    timestamp,
                    "selected",
                    message,
                    line_no,
                    vt=selected.group("vt"),
                    desktop=selected.group("desktop"),
                )
            )
        elif STARTED_RE.search(message):
            started = STARTED_RE.search(message)
            assert started is not None
            events.append(
                Event(
                    timestamp,
                    "started",
                    message,
                    line_no,
                    ok=started.group("ok") == "true",
                )
            )
        elif HELPER_RE.search(message):
            helper = HELPER_RE.search(message)
            assert helper is not None
            code = 0 if helper.group("success") else int(helper.group("code"))
            events.append(Event(timestamp, "helper", message, line_no, code=code))
        elif FALLBACK_RE.search(message):
            events.append(Event(timestamp, "fallback", message, line_no))
        elif LOGOUT_RE.search(message):
            events.append(Event(timestamp, "logout", message, line_no))
        elif SHUTDOWN_RE.search(message):
            events.append(Event(timestamp, "shutdown", message, line_no))
    return events


def analyze(events: Iterable[Event]) -> Report:
    report = Report(events=list(events))
    current: Optional[Attempt] = None
    for event in report.events:
        if event.kind == "login":
            current = Attempt(event.ts, event.ts, "login")
            report.attempts.append(current)
            continue

        if event.kind == "selected":
            if current is None:
                current = Attempt(event.ts, None, "autologin")
                report.attempts.append(current)
            current.vt = event.vt
            current.desktop = event.desktop
            continue

        if event.kind == "started":
            if current is None:
                current = Attempt(event.ts, None, "autologin")
                report.attempts.append(current)
            current.session_started = event.ok
            current.started_ts = event.ts
            continue

        if event.kind == "helper":
            if current is None:
                if event.code == 2:
                    report.standalone_failures.append(
                        Failure(
                            "helper-exit-2",
                            event.ts,
                            "Auth: sddm-helper exited with 2 with no preceding login/session start",
                        )
                    )
                continue
            current.helper_events.append(event)
            continue

        if event.kind == "fallback":
            report.fallbacks.append(event)
            if current is not None:
                current.fallback_events.append(event)
            else:
                report.standalone_failures.append(
                    Failure(
                        "x11-user-fallback",
                        event.ts,
                        "DisplayServer=x11-user fallback before any login",
                    )
                )
            continue

        if event.kind == "logout":
            if current is not None:
                current.logout_ts = event.ts
            continue

        if event.kind == "shutdown":
            if current is not None:
                current.shutdown_ts = event.ts

    # A fallback after the current attempt belongs to that attempt; one before
    # the first login is already a standalone failure.
    for attempt in report.attempts:
        if attempt.session_started is False:
            attempt.failures.append(
                Failure(
                    "session-started-false",
                    attempt.started_ts or attempt.start,
                    "Session started false",
                    attempt.start,
                )
            )
        for event in attempt.helper_events:
            if event.code == 2:
                attempt.failures.append(
                    Failure(
                        "helper-exit-2",
                        event.ts,
                        "Auth: sddm-helper exited with 2"
                        + _delta_detail(attempt.start, event.ts),
                        attempt.start,
                    )
                )
        for event in attempt.fallback_events:
            attempt.failures.append(
                Failure(
                    "x11-user-fallback",
                    event.ts,
                    "DisplayServer=x11-user fallback"
                    + _delta_detail(attempt.start, event.ts),
                    attempt.start,
                )
            )
        if (
            attempt.logout_ts is not None
            and attempt.logout_ts - attempt.start <= BOUNCE_WINDOW
            and not _has_shutdown_between(attempt)
        ):
            attempt.failures.append(
                Failure(
                    "early-logout",
                    attempt.logout_ts,
                    "session logged out"
                    + _delta_detail(attempt.start, attempt.logout_ts)
                    + " without a shutdown/reboot request",
                    attempt.start,
                )
            )
    return report


def _has_shutdown_between(attempt: Attempt) -> bool:
    return (
        attempt.shutdown_ts is not None
        and attempt.logout_ts is not None
        and attempt.start <= attempt.shutdown_ts <= attempt.logout_ts
    )


def _delta_detail(start: datetime, end: datetime) -> str:
    seconds = int((end - start).total_seconds())
    return " (+{}s)".format(seconds)


def _fmt_time(dt: Optional[datetime]) -> str:
    if dt is None:
        return "-"
    return dt.strftime("%H:%M:%S")


def _fmt_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return "-"
    if seconds < 60:
        return "{}s".format(seconds)
    return "{}m{:02d}s".format(seconds // 60, seconds % 60)


def _fmt_helper(attempt: Attempt) -> str:
    code = attempt.helper_code
    if code is None:
        return "-"
    if code == 0:
        return "ok"
    return str(code)


def render_table(report: Report) -> str:
    lines: List[str] = []
    window = "boot {}".format(report.boot) if report.boot is not None else "since {}".format(
        report.since
    )
    lines.append("SDDM session-bounce check — {} — {} attempt(s)".format(window, len(report.attempts)))
    lines.append("")
    lines.append("LOGIN      VT  STARTED  HELPER  DURATION  VERDICT")
    for attempt in report.attempts:
        login = _fmt_time(attempt.login_ts or attempt.start)
        if attempt.login_ts is None:
            login = login + "*"
        lines.append(
            "{:<10} {:<3} {:<8} {:<7} {:<9} {}".format(
                login,
                attempt.vt or "-",
                "true"
                if attempt.session_started is True
                else "false"
                if attempt.session_started is False
                else "-",
                _fmt_helper(attempt),
                _fmt_duration(attempt.duration_seconds),
                "FAIL" if attempt.failures else "PASS",
            )
        )
    if not report.attempts:
        lines.append("(no login or session-start events in window)")

    if report.all_failures:
        lines.append("")
        lines.append("FAILURES")
        for failure in report.all_failures:
            lines.append(
                "  {}  {:<22} {}".format(
                    failure.ts.strftime("%H:%M:%S"), failure.kind, failure.detail
                )
            )

    if report.fallbacks:
        lines.append("")
        lines.append(
            "DisplayServer=x11-user fallback line(s): {}".format(len(report.fallbacks))
        )
        for event in report.fallbacks:
            lines.append("  {}  {}".format(event.ts.strftime("%H:%M:%S"), event.message))
    if any(attempt.login_ts is None for attempt in report.attempts):
        lines.append("")
        lines.append("* no greeter Login line (autologin); time is the session start")

    lines.append("")
    if report.ok:
        lines.append(
            "RESULT: PASS — {} login attempt(s), no bounce or x11-user fallback".format(
                len(report.attempts)
            )
        )
    else:
        lines.append(
            "RESULT: FAIL — {} failed login attempt(s) of {}; {} x11-user fallback line(s)".format(
                len(report.failed_attempts),
                len(report.attempts),
                len(report.fallbacks),
            )
        )
    return "\n".join(lines)


def _run_journal(boot: Optional[int], since: Optional[str]) -> Tuple[str, List[str]]:
    command = ["journalctl", "-u", "sddm", "--no-pager", "--output=short-iso"]
    if boot is not None:
        command.extend(["--boot", str(boot)])
    if since:
        command.extend(["--since", since])
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise RuntimeError("journalctl not found in PATH")
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            "journalctl failed (exit {}): {}".format(completed.returncode, detail)
        )
    return completed.stdout, command


RED_FIXTURE = """\
2026-10-26T08:29:29-05:00 host sddm[1010]: Message received from greeter: Login
2026-10-26T08:29:29-05:00 host sddm[1010]: Session "/usr/share/wayland-sessions/hyprland-uwsm.desktop" selected, command: "uwsm start -e -D Hyprland hyprland.desktop" for VT 2
2026-10-26T08:29:31-05:00 host sddm[1010]: Auth: sddm-helper exited successfully
2026-10-26T08:29:59-05:00 host sddm[1010]: Session started false
2026-10-26T08:30:59-05:00 host sddm[1010]: Auth: sddm-helper exited with 2
2026-10-26T08:31:00-05:00 host sddm[1010]: Failed to launch the display server, falling back to DisplayServer=x11-user
"""

GREEN_FIXTURE = """\
2026-10-26T08:35:01-05:00 host sddm[1010]: Message received from greeter: Login
2026-10-26T08:35:01-05:00 host sddm[1010]: Session "/usr/share/wayland-sessions/hyprland-uwsm.desktop" selected, command: "uwsm start -e -D Hyprland hyprland.desktop" for VT 2
2026-10-26T08:35:01-05:00 host sddm[1010]: Session started true
2026-10-26T08:35:01-05:00 host sddm[1010]: Auth: sddm-helper exited successfully
"""

FALLBACK_ONLY_FIXTURE = """\
2026-10-26T08:28:27-05:00 host sddm[1010]: Failed to launch the display server, falling back to DisplayServer=x11-user
"""

EARLY_LOGOUT_FIXTURE = """\
2026-10-26T10:00:00-05:00 host sddm[1010]: Message received from greeter: Login
2026-10-26T10:00:00-05:00 host sddm[1010]: Session started true
2026-10-26T10:00:01-05:00 host sddm[1010]: Auth: sddm-helper exited successfully
2026-10-26T10:01:00-05:00 host sddm[1010]: Session 2 logged out
"""

SHUTDOWN_LOGOUT_FIXTURE = """\
2026-10-26T10:00:00-05:00 host sddm[1010]: Message received from greeter: Login
2026-10-26T10:00:00-05:00 host sddm[1010]: Session started true
2026-10-26T10:00:01-05:00 host sddm[1010]: Auth: sddm-helper exited successfully
2026-10-26T10:00:30-05:00 host systemd[1]: Stopping Simple Desktop Display Manager...
2026-10-26T10:01:00-05:00 host sddm[1010]: Session 2 logged out
"""

AUTOLOGIN_GREEN_FIXTURE = """\
2026-10-26T11:00:00-05:00 host sddm[1010]: Session "/usr/share/wayland-sessions/hyprland-uwsm.desktop" selected, command: "uwsm start -e -D Hyprland hyprland.desktop" for VT 2
2026-10-26T11:00:00-05:00 host sddm[1010]: Session started true
2026-10-26T11:00:01-05:00 host sddm[1010]: Auth: sddm-helper exited successfully
"""

AUTOLOGIN_RED_FIXTURE = """\
2026-10-26T11:00:00-05:00 host sddm[1010]: Session "/usr/share/wayland-sessions/hyprland-uwsm.desktop" selected, command: "uwsm start -e -D Hyprland hyprland.desktop" for VT 2
2026-10-26T11:00:30-05:00 host sddm[1010]: Session started false
2026-10-26T11:01:30-05:00 host sddm[1010]: Auth: sddm-helper exited with 2
"""

# journalctl's default `short` format (locale month abbreviations are
# lower-case on this host).  The parser must not depend on --output=short-iso.
SYSLOG_SHORT_GREEN_FIXTURE = """\
oct 26 08:35:01 host sddm[1010]: Message received from greeter: Login
oct 26 08:35:01 host sddm[1010]: Session "/usr/share/wayland-sessions/hyprland-uwsm.desktop" selected, command: "uwsm start -e -D Hyprland hyprland.desktop" for VT 2
oct 26 08:35:01 host sddm[1010]: Session started true
oct 26 08:35:01 host sddm[1010]: Auth: sddm-helper exited successfully
"""


def _self_test() -> int:
    cases = [
        ("red fixture (real 08:29:29→08:30:59 bounce)", RED_FIXTURE, False),
        ("green fixture (login → Session started true)", GREEN_FIXTURE, True),
        ("fallback-only fixture", FALLBACK_ONLY_FIXTURE, False),
        ("early-logout fixture", EARLY_LOGOUT_FIXTURE, False),
        ("shutdown-logout fixture", SHUTDOWN_LOGOUT_FIXTURE, True),
        ("autologin green fixture", AUTOLOGIN_GREEN_FIXTURE, True),
        ("autologin red fixture", AUTOLOGIN_RED_FIXTURE, False),
        ("journalctl short-format fixture", SYSLOG_SHORT_GREEN_FIXTURE, True),
    ]
    passed = 0
    print("SELF-TEST — embedded red/green journal fixtures")
    for name, fixture, expected_ok in cases:
        report = analyze(parse_journal(fixture))
        actual_ok = report.ok
        status = "PASS" if actual_ok == expected_ok else "FAIL"
        if status == "PASS":
            passed += 1
        print(
            "  [{}] {}: expected {}, got {} ({} attempt(s), {} failure(s))".format(
                status,
                name,
                "green" if expected_ok else "red",
                "green" if actual_ok else "red",
                len(report.attempts),
                len(report.all_failures),
            )
        )

    # The red fixture must fail for the real reasons, not by accident.
    red = analyze(parse_journal(RED_FIXTURE))
    red_kinds = {failure.kind for failure in red.all_failures}
    required = {"session-started-false", "helper-exit-2", "x11-user-fallback"}
    missing = sorted(required - red_kinds)
    red_specific = not missing
    print(
        "  [{}] red fixture reasons: {}".format(
            "PASS" if red_specific else "FAIL", ", ".join(sorted(red_kinds))
        )
    )
    if red_specific:
        passed += 1

    green = analyze(parse_journal(GREEN_FIXTURE))
    green_specific = len(green.attempts) == 1 and green.ok
    print(
        "  [{}] green fixture: 1 clean attempt".format(
            "PASS" if green_specific else "FAIL"
        )
    )
    if green_specific:
        passed += 1

    total = len(cases) + 2
    print("SELF-TEST: {} ({}/{})".format("PASS" if passed == total else "FAIL", passed, total))
    return 0 if passed == total else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail on an SDDM session bounce (Session started false, helper exit 2, x11-user fallback, early logout)."
    )
    parser.add_argument(
        "--boot",
        type=int,
        default=None,
        help="journalctl boot index: 0 = current boot (default), -1 = previous boot",
    )
    parser.add_argument(
        "--since",
        default=None,
        help='journalctl --since value (e.g. "today", "2026-10-26 08:00:00"); disables the default --boot 0',
    )
    parser.add_argument(
        "--json", action="store_true", help="print the report as JSON"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run embedded red/green fixtures and exit 0 when they behave",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help="analyze saved journalctl -u sddm text instead of invoking journalctl",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.self_test:
        return _self_test()

    boot = args.boot
    if boot is None and args.since is None:
        boot = 0

    command: Optional[List[str]] = None
    try:
        if args.log_file:
            with open(args.log_file, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        else:
            text, command = _run_journal(boot, args.since)
    except (OSError, RuntimeError) as error:
        message = str(error)
        if args.json:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": message,
                        "boot": boot,
                        "since": args.since,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print("ERROR: {}".format(message), file=sys.stderr)
            print(
                "HINT: journal access needs a user in systemd-journal (or reading as root); "
                "the checker never escalates itself.",
                file=sys.stderr,
            )
        return 2

    report = analyze(parse_journal(text))
    report.boot = boot
    report.since = args.since
    report.journal_command = command

    if args.json:
        print(json.dumps(report.as_json(), indent=2, sort_keys=True))
    else:
        print(render_table(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
