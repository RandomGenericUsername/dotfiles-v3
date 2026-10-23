#!/usr/bin/env python3
"""Run the routing edge-case check with silent, temporary null sinks.

This temporarily changes the PipeWire default only while no playback streams
are present, uses a generated silent stream, restores the original default in a
finally block, and unloads its temporary null-sink modules. Run only in the
interactive desktop session being evaluated.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from collections import deque


def run(*args: str, check: bool = True) -> str:
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    if check and result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def snapshot() -> list[dict]:
    return json.loads(run("pw-dump"))


def objects_of_type(objects: list[dict], name: str) -> list[dict]:
    return [o for o in objects if o.get("type", "").endswith(name)]


def properties(obj: dict) -> dict:
    return obj.get("info", {}).get("props", {})


def node_by_name(objects: list[dict], name: str) -> dict | None:
    return next((o for o in objects_of_type(objects, "Node") if properties(o).get("node.name") == name), None)


def linked_sink(objects: list[dict], stream_id: int) -> int | None:
    links = objects_of_type(objects, "Link")
    for link in links:
        props = properties(link)
        if str(props.get("link.output.node")) == str(stream_id):
            try:
                return int(props["link.input.node"])
            except (KeyError, TypeError, ValueError):
                pass
    return None


def stream_id_for_app(objects: list[dict], app_name: str) -> int | None:
    for node in objects_of_type(objects, "Node"):
        props = properties(node)
        if props.get("application.name") == app_name and props.get("media.class", "").startswith("Stream/Output/Audio"):
            return int(node["id"])
    return None


def wait_for(label: str, predicate, timeout: float = 5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        objects = snapshot()
        value = predicate(objects)
        if value is not None and value is not False:
            print(f"PASS {label}: {value}")
            return value
        time.sleep(0.1)
    raise RuntimeError(f"timed out waiting for {label}")


class Monitor:
    def __init__(self):
        self.process = subprocess.Popen(["pw-dump", "--monitor"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.lines: deque[str] = deque(maxlen=5000)
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.lines.append(line.rstrip())

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)
        self.thread.join(timeout=1)

    def mentions(self, tokens: list[str]) -> int:
        return sum(any(token in line for token in tokens) for line in self.lines)


def start_stream(app_name: str, target: str | None = None) -> subprocess.Popen:
    args = ["pw-cat", "--playback", "--raw", "--rate", "48000", "--channels", "2", "--format", "s16"]
    if target is not None:
        args += ["--target", target]
    args += ["--properties", f"application.name={app_name} application.process.binary=audio-route-gate", "/dev/zero"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)


def stop_stream(process: subprocess.Popen | None):
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def main() -> int:
    original_default: int | None = None
    module_ids: list[str] = []
    stream: subprocess.Popen | None = None
    monitor: Monitor | None = None
    try:
        status = run("wpctl", "status", "-n")
        audio_section = status.split("Audio", 1)[1].split("Video", 1)[0]
        sink_section = audio_section.split("Sinks:", 1)[1].split("Sources:", 1)[0]
        match = re.search(r"\*\s*(\d+)\.", sink_section)
        if not match:
            raise RuntimeError("could not identify the current default audio sink")
        original_default = int(match.group(1))
        initial = snapshot()
        active = [
            o for o in objects_of_type(initial, "Node")
            if properties(o).get("media.class", "").startswith("Stream/Output/Audio")
        ]
        if active:
            raise RuntimeError("playback streams are active; aborting without changing the default")
        print(f"PASS safety precondition: no playback streams; original default node {original_default}")

        for suffix in ("A", "C"):
            module_id = run("pactl", "load-module", "module-null-sink", f"sink_name=codex_route_gate_{suffix}", f"sink_properties=device.description=CodexRouteGate{suffix}")
            module_ids.append(module_id)

        name_a = "codex_route_gate_A"
        name_c = "codex_route_gate_C"
        id_a = wait_for("temporary silent sink A appears", lambda o: (node_by_name(o, name_a) or {}).get("id"))
        id_c = wait_for("temporary silent sink C appears", lambda o: (node_by_name(o, name_c) or {}).get("id"))
        id_a, id_c = int(id_a), int(id_c)
        monitor = Monitor()

        # Ordinary app path: no explicit target or saved per-app override.
        run("wpctl", "set-default", str(id_a))
        stream = start_stream("CodexRouteGate-Follows")
        stream_id = wait_for("new no-override app stream appears", lambda o: stream_id_for_app(o, "CodexRouteGate-Follows"))
        wait_for("new app initially links to preferred A", lambda o: linked_sink(o, stream_id) == id_a)
        run("wpctl", "set-default", str(id_c))
        wait_for("new app follows preferred change A to C", lambda o: linked_sink(o, stream_id) == id_c)
        stop_stream(stream)
        stream = None

        # Edge case: an explicit per-app target equals the current default.
        run("wpctl", "set-default", str(id_a))
        stream = start_stream("CodexRouteGate-ExplicitSameDefault", name_a)
        explicit_id = wait_for("explicit app stream appears", lambda o: stream_id_for_app(o, "CodexRouteGate-ExplicitSameDefault"))
        wait_for("explicit route initially links to A", lambda o: linked_sink(o, explicit_id) == id_a)
        run("wpctl", "set-default", str(id_c))
        moved_sink = wait_for(
            "explicit-same-default stream settles after preferred change",
            lambda o: linked_sink(o, explicit_id),
        )
        outcome = "FOLLOWED_DEFAULT" if moved_sink == id_c else "STAYED_EXPLICIT"
        print(f"RESULT explicit target A while A was preferred, then preferred C: {outcome} (sink node {moved_sink})")
        stop_stream(stream)
        stream = None

        # Reassertion path used by the app-owned intent registry: target A while
        # A is no longer preferred, then change the default again.
        run("wpctl", "set-default", str(id_c))
        stream = start_stream("CodexRouteGate-Reasserted", name_a)
        reasserted_id = wait_for("reasserted explicit A stream appears while C is preferred", lambda o: stream_id_for_app(o, "CodexRouteGate-Reasserted"))
        wait_for("explicit A route is restored", lambda o: linked_sink(o, reasserted_id) == id_a)
        run("wpctl", "set-default", str(original_default))
        wait_for("restored explicit A remains routed after another default change", lambda o: linked_sink(o, reasserted_id) == id_a)
        stop_stream(stream)
        stream = None

        count = monitor.mentions([name_a, name_c, "CodexRouteGate-"])
        monitor.close()
        monitor = None
        print(f"{'PASS' if count else 'WARN'} pw-dump monitor captured matching route events: {count} matching lines")
        print("PASS test streams were silent and temporary")
        return 0
    except Exception as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    finally:
        stop_stream(stream)
        if monitor is not None:
            monitor.close()
        if original_default is not None:
            subprocess.run(["wpctl", "set-default", str(original_default)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        for module_id in reversed(module_ids):
            subprocess.run(["pactl", "unload-module", module_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
