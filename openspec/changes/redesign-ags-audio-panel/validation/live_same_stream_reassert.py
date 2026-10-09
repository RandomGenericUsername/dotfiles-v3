#!/usr/bin/env python3
"""Reversible live route test; routes active apps briefly through silent sinks."""
import json, re, subprocess, threading, time
from collections import deque

def run(*args):
    p = subprocess.run(args, text=True, capture_output=True, timeout=10)
    if p.returncode:
        raise RuntimeError(f"{args[0]}: {p.stderr.strip() or p.stdout.strip()}")
    return p.stdout.strip()

def dump(): return json.loads(run("pw-dump"))
def props(o): return o.get("info", {}).get("props", {})
def of_type(xs, name): return [o for o in xs if o.get("type", "").endswith(name)]
def sink_id(xs, name):
    o = next(o for o in of_type(xs, "Node") if props(o).get("node.name") == name)
    return int(o["id"])
def link_target(xs, node_id):
    for o in of_type(xs, "Link"):
        p = props(o)
        if str(p.get("link.output.node")) == str(node_id):
            return int(p["link.input.node"])
    return None
def wait(label, predicate, timeout=6):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = predicate(dump())
        if v:
            print("PASS", label, v if v is not True else "")
            return v
        time.sleep(.1)
    raise RuntimeError("timed out: " + label)

class Monitor:
    def __init__(self):
        self.p = subprocess.Popen(["pw-dump", "--monitor"], stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True)
        self.lines = deque(maxlen=12000)
        self.t = threading.Thread(target=self.read, daemon=True); self.t.start()
    def read(self):
        for line in self.p.stdout: self.lines.append(line.rstrip())
    def close(self):
        self.p.terminate()
        try: self.p.wait(timeout=2)
        except subprocess.TimeoutExpired: self.p.kill(); self.p.wait()
        self.t.join(timeout=1)

modules=[]; stream=None; monitor=None; original=None; test_index=None
try:
    st=run("wpctl","status","-n")
    sec=st.split("Audio",1)[1].split("Video",1)[0].split("Sinks:",1)[1].split("Sources:",1)[0]
    original=int(re.search(r"\*\s*(\d+)\.",sec).group(1))
    before=dump()
    original_links={int(o["id"]): link_target(before,int(o["id"])) for o in of_type(before,"Node")
                    if props(o).get("media.class","").startswith("Stream/Output/Audio")}
    print("SAVED default",original,"active stream routes",original_links)
    for suffix in ("A","B"):
        modules.append(run("pactl","load-module","module-null-sink",f"sink_name=codex_same_stream_{suffix}",f"sink_properties=device.description=CodexSameStream{suffix}"))
    a=sink_id(dump(),"codex_same_stream_A"); b=sink_id(dump(),"codex_same_stream_B")
    monitor=Monitor(); time.sleep(.25)
    run("wpctl","set-default",str(a))
    stream=subprocess.Popen(["pw-cat","--playback","--raw","--rate","48000","--channels","2","--format","s16","--target","codex_same_stream_A","--properties","application.name=CodexSameStream application.process.binary=route-validation","/dev/zero"],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    sid=wait("same test stream created",lambda xs: next((int(o["id"]) for o in of_type(xs,"Node") if props(o).get("application.name")=="CodexSameStream"),None))
    wait("stream initially linked to default A",lambda xs: link_target(xs,sid)==a)
    run("wpctl","set-default",str(b))
    wait("WirePlumber moves same stream when its old target was default A",lambda xs: link_target(xs,sid)==b)
    inputs=json.loads(run("pactl","-f","json","list","sink-inputs"))
    inp=next(x for x in inputs if x.get("properties",{}).get("application.name")=="CodexSameStream")
    test_index=int(inp["index"])
    run("pactl","move-sink-input",str(test_index),"codex_same_stream_A")
    wait("same running stream explicitly reasserted to A",lambda xs: link_target(xs,sid)==a)
    run("wpctl","set-default",str(original))
    wait("same stream retains explicit A across another default change",lambda xs: link_target(xs,sid)==a)
    print("PASS same-stream route reassertion at PipeWire/Pulse command layer")
    time.sleep(.3)
finally:
    # Restore the real default before removing the silent endpoints.
    if original is not None:
        subprocess.run(["wpctl","set-default",str(original)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
    if stream is not None:
        stream.terminate()
        try: stream.wait(timeout=2)
        except subprocess.TimeoutExpired: stream.kill(); stream.wait()
    time.sleep(.2)
    if monitor is not None:
        monitor.close()
        lines=list(monitor.lines)
        relevant=[x for x in lines if any(t in x.lower() for t in ("default.audio.sink","codex_same_stream","metadata"))]
        print("MONITOR lines",len(lines),"relevant",len(relevant))
        print("MONITOR sample",json.dumps(relevant[-35:]))
    for mid in reversed(modules):
        subprocess.run(["pactl","unload-module",mid],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
    time.sleep(.4)
    if original is not None:
        final=dump()
        st=run("wpctl","status","-n")
        sec=st.split("Audio",1)[1].split("Video",1)[0].split("Sinks:",1)[1].split("Sources:",1)[0]
        restored=int(re.search(r"\*\s*(\d+)\.",sec).group(1))
        print("RESTORE default",restored,"active stream routes",{int(o["id"]):link_target(final,int(o["id"])) for o in of_type(final,"Node") if props(o).get("media.class","").startswith("Stream/Output/Audio")})
        if restored != original: raise RuntimeError("failed to restore the original default output")
