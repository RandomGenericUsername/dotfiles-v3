import json, pathlib, subprocess, time

PLAYER = "firefox.instance_1_853"
OUT = pathlib.Path("/tmp/audio-seek-capture-v2")
OUT.mkdir(exist_ok=True)

def cmd(*args):
    p = subprocess.run(args, text=True, capture_output=True, timeout=6)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    return p.stdout.strip()

def snap():
    return json.loads(cmd("ags", "request", "audio-debug"))

def row(s):
    return next((r for r in s.get("rows", []) if r.get("app") == "firefox"), None)

def frame(name):
    cmd("grim", "-g", "1390,50 370x460", str(OUT / f"{name}.png"))

initial_pos = float(cmd("playerctl", f"--player={PLAYER}", "position"))
initial_meta = cmd("playerctl", f"--player={PLAYER}", "metadata", "--format", "{{xesam:title}}|{{xesam:url}}")
initial = snap()
print("BEFORE", json.dumps({"position": initial_pos, "meta": initial_meta, "row": row(initial), "render": initial.get("render")}))
frame("before")
try:
    # Current Firefox track is 6:34. Seek only 15 seconds from its reported 0 position.
    cmd("playerctl", f"--player={PLAYER}", "position", "15")
    for i in range(8):
        time.sleep(.12)
        s = snap()
        meta = cmd("playerctl", f"--player={PLAYER}", "metadata", "--format", "{{xesam:title}}|{{xesam:url}}")
        print("FRAME", i, json.dumps({"meta": meta, "row": row(s), "render": s.get("render")}))
        frame(f"seek-{i:02d}")
finally:
    meta = cmd("playerctl", f"--player={PLAYER}", "metadata", "--format", "{{xesam:title}}|{{xesam:url}}")
    if meta == initial_meta:
        cmd("playerctl", f"--player={PLAYER}", "position", str(initial_pos))
    time.sleep(.5)
    restored = snap()
    print("AFTER", json.dumps({"position": cmd("playerctl", f"--player={PLAYER}", "position"), "meta": cmd("playerctl", f"--player={PLAYER}", "metadata", "--format", "{{xesam:title}}|{{xesam:url}}"), "row": row(restored), "render": restored.get("render")}))
    frame("after")
print("CAPTURES", OUT)
