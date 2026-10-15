#!/usr/bin/env python3
"""Build v8 = the v7 component studio + a "Live" tab that shows real btop.

Starts from _v5_template.html (which already has the gradient editor):
  - strip the old static Truth pane,
  - add a Components / Live tab pair; the Live pane POSTs the current theme to
    the studio server (localhost:8799) and shows the real btop frame,
  - inject the parsed btop config.
Writes btop-theme-studio-v8.html.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess

HERE = pathlib.Path(__file__).resolve().parent


def default_cfg() -> tuple[str, str]:
    out = subprocess.run(["btop", "--default-config"], capture_output=True, text=True).stdout
    p = re.search(r'^presets = "(.*)"', out, re.M)
    s = re.search(r'^shown_boxes = "(.*)"', out, re.M)
    return (p.group(1) if p else ""), (s.group(1) if s else "cpu mem net proc")


def parse_presets(raw: str) -> dict:
    defs = {"0": {"label": "Preset 0 — all boxes shown (btop rule)",
                  "boxes": {"cpu": 0, "gpu": 0, "mem": 0, "net": 0, "disks": 0, "proc": 0}, "symbol": "default"}}
    for i, group in enumerate(raw.split(), start=1):
        boxes, syms = {}, []
        for entry in group.split(","):
            parts = entry.split(":")
            if not parts or not parts[0]:
                continue
            boxes[parts[0]] = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            syms.append(parts[2] if len(parts) > 2 else "default")
        if "cpu" in boxes and "gpu" not in boxes:
            boxes["gpu"] = boxes["cpu"]
        defs[str(i)] = {"label": f"Preset {i} — {group}", "boxes": boxes, "symbol": syms[0] if syms else "default"}
    return defs


TABS = """      <div class="spacer"></div>
      <button class="toggle on" id="tabComp">Components</button>
      <button class="toggle" id="tabLive">Live</button>"""

PANE = """      <div id="paneComponents">
      <div class="stage-cap" id="cap"></div>
      <div class="btop" id="btop"></div>
      <div class="off-note" id="offnote"></div>
      <div class="anat" id="anat"></div>
      </div>
      <div id="paneLive" style="display:none">
        <div class="stage-cap" id="capLive">Live — real <b>btop</b> on a pty (a fresh capture per edit)</div>
        <pre class="live" id="liveFrame"></pre>
        <div class="off-note" id="liveStatus"></div>
      </div>"""

LIVE_JS = """const LIVE_URL = "http://localhost:8799";
let liveTab = false, liveTimer = null;
function hexMap(){const o={};for(const k in curTheme.map){o[k]=curTheme.map[k]===""?"":R(k);}return o;}
function refreshLive(){
  const st=document.getElementById("liveStatus"), fr=document.getElementById("liveFrame");
  st.textContent="rendering real btop\\u2026";
  fetch(LIVE_URL+"/edit",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({preset:preset,keys:hexMap()})})
    .then(r=>r.json()).then(j=>{fr.innerHTML=j.frame;st.textContent="preset "+preset+" \\u00b7 boxes: "+j.boxes.join(" ");})
    .catch(()=>{st.textContent="live server not reachable at "+LIVE_URL+" \\u2014 start it with: uv run --with pyte python3 studio_server.py";});
}
function liveMaybe(){if(!liveTab)return;if(liveTimer)clearTimeout(liveTimer);liveTimer=setTimeout(refreshLive,250);}
const _origRenderAll = renderAll;
renderAll = function(){ _origRenderAll(); liveMaybe(); };
document.getElementById("tabComp").onclick=()=>{liveTab=false;
  document.getElementById("paneComponents").style.display="block";
  document.getElementById("paneLive").style.display="none";
  document.getElementById("tabComp").classList.add("on");document.getElementById("tabLive").classList.remove("on");};
document.getElementById("tabLive").onclick=()=>{liveTab=true;
  document.getElementById("paneComponents").style.display="none";
  document.getElementById("paneLive").style.display="block";
  document.getElementById("tabLive").classList.add("on");document.getElementById("tabComp").classList.remove("on");
  refreshLive();};
// pull the live palette so the swatches (incl. color0-15) match the current wallpaper
fetch(LIVE_URL+"/state").then(r=>r.json()).then(s=>{
  if(s.ramp&&s.ramp.length)STOPS=s.ramp;
  if(s.colors&&s.colors.length)COLORS16=s.colors;
  if(s.bg&&s.fg)NAMED={background:s.bg,foreground:s.fg,cursor:s.fg};
  renderAll();
}).catch(()=>{});
"""


def main() -> int:
    raw, shown = default_cfg()
    defs = parse_presets(raw)
    tpl = (HERE / "_v5_template.html").read_text()

    # strip the static truth pane + its wiring
    tpl = re.sub(r'\s*<div class="truth" id="truth">.*?<div class="grid2"><!--__TRUTH__--></div>\s*</div>', "", tpl, flags=re.S)
    tpl = tpl.replace('      <button class="toggle on" id="tTruth">Show Truth pane</button>\n', "")
    tpl = tpl.replace("highlight=true,showTruth=true,themeSeq=1", "highlight=true,themeSeq=1")
    tpl = tpl.replace('function renderTruth(){document.getElementById("truth").style.display=showTruth?"block":"none";}\n', "")
    tpl = tpl.replace("renderDiff();renderTruth();", "renderDiff();")
    tpl = tpl.replace('document.getElementById("tTruth").onclick=(e)=>{showTruth=!showTruth;e.target.classList.toggle("on",showTruth);renderTruth();};\n', "")

    # tab bar
    assert tpl.count('      <div class="spacer"></div>') == 1, "spacer anchor"
    tpl = tpl.replace('      <div class="spacer"></div>', TABS)

    # panes
    old_pane = ('      <div class="stage-cap" id="cap"></div>\n'
                '      <div class="btop" id="btop"></div>\n'
                '      <div class="off-note" id="offnote"></div>\n'
                '      <div class="anat" id="anat"></div>')
    assert old_pane in tpl, "canvas pane anchor"
    tpl = tpl.replace(old_pane, PANE)

    # live-frame CSS
    anchor = '.stage-cap b{color:var(--fg);}'
    assert anchor in tpl, "css anchor"
    tpl = tpl.replace(anchor, anchor + '\n  .live{font-family:"JetBrainsMono Nerd Font","Adwaita Mono","DejaVu Sans Mono",ui-monospace,monospace;font-variant-ligatures:none;font-size:10px;line-height:1.02;white-space:pre;letter-spacing:0;border:1px solid #ffffff18;border-radius:6px;padding:8px;display:inline-block;min-width:1180px;background:#00000040;}')

    # live JS + tab wiring (before the final renderAll())
    assert tpl.rstrip().endswith("renderAll();\n</script>\n</body>\n</html>"), "tail anchor"
    tpl = tpl.replace("renderAll();\n</script>", LIVE_JS + "\nrenderAll();\n</script>")

    # note text
    tpl = re.sub(r'<div class="note">.*?</div>\n',
                 '<div class="note">UI mock v8 — <b>Components</b> (the labelled schematic, instant) and a '
                 '<b>Live</b> tab (the real btop binary, ~2&nbsp;s per edit). Both driven by your real '
                 '<code>btop.conf</code> presets. Edit on Components; verify on Live.</div>\n',
                 tpl, count=1, flags=re.S)

    config_js = ("const PRESETS_RAW = " + json.dumps(raw) + ";\n"
                 "const SHOWN_BOXES = " + json.dumps(shown) + ";\n"
                 "const PRESET_DEFS = " + json.dumps(defs) + ";\n")
    out = tpl.replace("/*__CONFIG__*/", config_js)

    kw = json.loads((HERE / "key_widgets.json").read_text())
    inject = ("const KEY_WIDGETS = " + json.dumps(kw["keys"]) + ";\n"
              "for(const k in KEY_WIDGETS){const m=KEY_WIDGETS[k].modules;"
              "if(WIDGETS[k])WIDGETS[k].mods=m;else WIDGETS[k]={paints:(SURFACE[k]||k),mods:m};}\n")
    out = out.replace("/*__KEYWIDGETS__*/", inject)
    (HERE / "btop-theme-studio-v8.html").write_text(out)
    print("wrote", HERE / "btop-theme-studio-v8.html", len(out), "chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
