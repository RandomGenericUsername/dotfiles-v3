#!/usr/bin/env python3
"""Verify isolated PipeWire stream/device controls and microphone activity.

Uses only temporary null sinks/sources and silent streams. It refuses to start
if an ordinary playback stream is active, does not change the physical default,
and removes every temporary object in a finally block. Run in the desktop
session being evaluated.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time


def run(*args: str, check: bool = True) -> str:
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=10)
    if check and result.returncode:
        raise RuntimeError(f"{' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def snapshot() -> list[dict]:
    return json.loads(run("pw-dump"))


def props(obj: dict) -> dict:
    return obj.get("info", {}).get("props", {})


def node_named(name: str, media_class: str | None = None) -> dict | None:
    for obj in snapshot():
        p = props(obj)
        if (obj.get("type", "").endswith("Node")
                and (p.get("node.name") == name or p.get("application.name") == name)
                and (media_class is None or p.get("media.class") == media_class)):
            return obj
    return None


def wait_for(label: str, predicate, timeout: float = 5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            detail = value.get("id", value) if isinstance(value, dict) else value
            print(f"PASS {label}: {detail}")
            return value
        time.sleep(0.1)
    raise RuntimeError(f"timed out waiting for {label}")


def volume(node_id: int) -> float:
    output = run("wpctl", "get-volume", str(node_id))
    import re
    match = re.search(r"Volume:\s*([0-9.]+)", output)
    if not match:
        raise RuntimeError(f"could not parse wpctl volume: {output}")
    return float(match.group(1))


def muted(node_id: int) -> bool:
    return "[MUTED]" in run("wpctl", "get-volume", str(node_id))


def ags_debug() -> dict:
    return json.loads(run("ags", "request", "audio-debug"))


def close(process: subprocess.Popen | None):
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def stream_command(mode: str, target: str, app: str) -> subprocess.Popen:
    args = ["pw-cat", "--raw", "--rate", "48000", "--channels", "2",
            "--format", "s16", "--target", target,
            "--properties", f"application.name={app} application.process.binary=audio-controls-gate"]
    if mode == "playback":
        args += ["--playback", "/dev/zero"]
    else:
        args += ["--record", "/dev/null"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)


def main() -> int:
    modules: list[str] = []
    processes: list[subprocess.Popen] = []
    original_default: int | None = None
    try:
        status = run("wpctl", "status", "-n")
        audio = status.split("Audio", 1)[1].split("Video", 1)[0]
        sinks = audio.split("Sinks:", 1)[1].split("Sources:", 1)[0]
        match = re.search(r"\*\s*(\d+)\.", sinks)
        if not match:
            raise RuntimeError("could not identify original default output")
        original_default = int(match.group(1))
        active = [o for o in snapshot() if o.get("type", "").endswith("Node")
                  and props(o).get("media.class") == "Stream/Output/Audio"]
        if active:
            raise RuntimeError("playback stream already active; aborting without changes")
        print("PASS safety precondition: no playback streams")

        modules.append(run("pactl", "load-module", "module-null-sink",
                           "sink_name=codex_controls_A", "sink_properties=device.description=CodexControlsA"))
        modules.append(run("pactl", "load-module", "module-null-sink",
                           "sink_name=codex_controls_B", "sink_properties=device.description=CodexControlsB"))
        sink_a = wait_for("temporary output A appears", lambda: node_named("codex_controls_A", "Audio/Sink"))
        sink_b = wait_for("temporary output B appears", lambda: node_named("codex_controls_B", "Audio/Sink"))
        source_name = next((line.split("\t")[1] for line in run("pactl", "list", "short", "sources").splitlines()
                            if "codex_controls_A.monitor" in line), None)
        if source_name is None:
            raise RuntimeError("temporary sink monitor source missing; sources: " + run("pactl", "list", "short", "sources"))
        ids = [int(sink_a["id"]), int(sink_b["id"])]

        processes.append(stream_command("playback", "codex_controls_A", "CodexControls-AppA"))
        processes.append(stream_command("playback", "codex_controls_B", "CodexControls-AppB"))
        app_a = wait_for("app A playback stream appears", lambda: node_named("CodexControls-AppA"))
        app_b = wait_for("app B playback stream appears", lambda: node_named("CodexControls-AppB"))
        app_a_id, app_b_id = int(app_a["id"]), int(app_b["id"])

        run("wpctl", "set-volume", str(app_a_id), "0.37")
        wait_for("app A stream volume changes to 37%", lambda: abs(volume(app_a_id) - .37) < .02)
        run("wpctl", "set-mute", str(app_a_id), "1")
        wait_for("app A mute toggles on", lambda: muted(app_a_id))
        if abs(volume(app_a_id) - .37) >= .02:
            raise RuntimeError("muting app A changed its stored level")
        print("PASS app A mute preserves its 37% stream level")
        diagnostic = ags_debug()
        wait_for("running AGS sees app A volume and mute state",
                 lambda: any(row.get("id") == app_a_id
                             and abs((row.get("volume") or 0) - .37) < .02
                             and row.get("mute") is True
                             for row in ags_debug().get("streams", [])))
        run("wpctl", "set-mute", str(app_a_id), "0")
        wait_for("app A mute toggles off", lambda: not muted(app_a_id))
        if abs(volume(app_b_id) - 1.0) >= .02:
            raise RuntimeError("changing app A changed app B stream volume")
        print("PASS app A stream gain is isolated from app B")

        run("wpctl", "set-volume", str(ids[0]), "0.42")
        wait_for("output A level changes to 42%", lambda: abs(volume(ids[0]) - .42) < .02)
        if abs(volume(ids[1]) - 1.0) >= .02:
            raise RuntimeError("changing output A changed output B level")
        print("PASS selected output level is device-scoped; output B remains unchanged")

        run("pactl", "set-source-volume", source_name, "31%")
        wait_for("temporary monitor input level changes to 31%",
                 lambda: "31%" in run("pactl", "get-source-volume", source_name))
        run("pactl", "set-source-mute", source_name, "1")
        wait_for("temporary monitor input mute toggles on",
                 lambda: run("pactl", "get-source-mute", source_name).endswith("yes"))
        run("pactl", "set-source-mute", source_name, "0")
        wait_for("temporary monitor input mute toggles off",
                 lambda: run("pactl", "get-source-mute", source_name).endswith("no"))

        processes.append(stream_command("record", source_name, "CodexControls-MicConsumer"))
        wait_for("microphone consumer stream appears", lambda: node_named("CodexControls-MicConsumer"))
        print("PASS synthetic microphone consumer is observable as a live capture stream")

        return 0
    except Exception as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    finally:
        for process in reversed(processes):
            close(process)
        if original_default is not None:
            subprocess.run(["wpctl", "set-default", str(original_default)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        for module_id in reversed(modules):
            subprocess.run(["pactl", "unload-module", module_id],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
