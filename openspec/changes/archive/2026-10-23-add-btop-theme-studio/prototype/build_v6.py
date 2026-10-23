#!/usr/bin/env python3
"""Build v6: the COMPONENT schematic as the single live pane.

Takes _v5_template.html, removes the static Truth pane entirely, injects the
parsed btop config (presets + shown_boxes), and writes btop-theme-studio-v6.html.
No btop capture needed -- the schematic recomputes live on every edit.
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


def main() -> int:
    raw, shown = default_cfg()
    defs = parse_presets(raw)
    tpl = (HERE / "_v5_template.html").read_text()

    # 1) drop the static Truth pane block
    tpl = re.sub(r'\s*<div class="truth" id="truth">.*?<div class="grid2"><!--__TRUTH__--></div>\s*</div>',
                 "", tpl, flags=re.S)
    # 2) drop its toggle + JS state/handler/render call
    tpl = tpl.replace('      <button class="toggle on" id="tTruth">Show Truth pane</button>\n', "")
    tpl = tpl.replace("highlight=true,showTruth=true,themeSeq=1", "highlight=true,themeSeq=1")
    tpl = tpl.replace('function renderTruth(){document.getElementById("truth").style.display=showTruth?"block":"none";}\n', "")
    tpl = tpl.replace("renderDiff();renderTruth();", "renderDiff();")
    tpl = tpl.replace('document.getElementById("tTruth").onclick=(e)=>{showTruth=!showTruth;e.target.classList.toggle("on",showTruth);renderTruth();};\n', "")
    # 3) re-word the banner
    tpl = re.sub(r'<div class="note">.*?</div>\n',
                 '<div class="note">UI mock v6 — the <b>component schematic</b> is the single live pane. '
                 'Layout + box set come from your real <b>btop.conf</b> (<code>shown_boxes</code> + parsed '
                 '<code>presets</code>); every edit re-renders it in place, and select a key to light up the '
                 'components it paints.</div>\n', tpl, count=1, flags=re.S)

    config_js = (
        "const PRESETS_RAW = " + json.dumps(raw) + ";\n"
        "const SHOWN_BOXES = " + json.dumps(shown) + ";\n"
        "const PRESET_DEFS = " + json.dumps(defs) + ";\n")
    out = tpl.replace("/*__CONFIG__*/", config_js)

    kw = json.loads((HERE / "key_widgets.json").read_text())
    inject = ("const KEY_WIDGETS = " + json.dumps(kw["keys"]) + ";\n"
              "for(const k in KEY_WIDGETS){const m=KEY_WIDGETS[k].modules;"
              "if(WIDGETS[k])WIDGETS[k].mods=m;else WIDGETS[k]={paints:(SURFACE[k]||k),mods:m};}\n")
    out = out.replace("/*__KEYWIDGETS__*/", inject)

    (HERE / "btop-theme-studio-v6.html").write_text(out)
    print("wrote", HERE / "btop-theme-studio-v6.html", len(out), "chars")
    print("presets:", {k: list(v["boxes"]) for k, v in defs.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
