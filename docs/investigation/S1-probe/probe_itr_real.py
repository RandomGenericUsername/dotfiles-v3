"""Real-`itr` invocation probe (no fake binary).

Usage (from src/runtime):
    uv run python ../../docs/investigation/S1-probe/probe_itr_real.py

Creates a private XDG config home whose itr settings point at a temp
templates dir, a temp color scheme, and a temp output dir, then lets the
adapter invoke the real `itr` on PATH.
"""

import os
from pathlib import Path

from runtime.adapters.hashing import canonical_hash_dir, hash_file, icons_entry_hash
from runtime.adapters.itr_adapter import ItrAdapter

root = Path("/tmp/opencode/probe_itr_real")
root.mkdir(parents=True, exist_ok=True)
xdg = root / "xdg"
(xdg / "itr").mkdir(parents=True, exist_ok=True)
templates = root / "templates"
(templates / "battery").mkdir(parents=True, exist_ok=True)
(templates / "battery" / "battery-0.svg").write_text(
    '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="{{background}}"/></svg>\n'
)
mappings = root / "icons.yaml"
mappings.write_text(
    "battery:\n"
    "  template_dir: battery/\n"
    "  output_dir: out/battery/\n"
    "  color_mappings:\n"
    "    background: background\n"
    "  variants:\n"
    "    - name: battery-0\n"
    "      template: battery-0.svg\n"
    "      output: battery-0.svg\n"
)
palette_hash = "a" * 64
palette_entry = root / "cache" / "palettes" / palette_hash
palette_entry.mkdir(parents=True, exist_ok=True)
(palette_entry / "colors.yaml").write_text(
    "special:\n  background: '#1a1a2e'\n  foreground: '#e0e0e0'\ncolors: []\n"
)
(xdg / "itr" / "settings.toml").write_text(
    f'[output]\noutput_dir = "{root / "default-out"}"\n'
    f'[templates]\ndir = "{templates}"\n'
    f'[color_scheme]\npath = "{palette_entry / "colors.yaml"}"\n'
)
os.environ["XDG_CONFIG_HOME"] = str(xdg)
th = canonical_hash_dir(templates)
mh = hash_file(mappings)
ih = icons_entry_hash(palette_hash, th, mh)
out = root / "cache" / "icons" / ih
adapter = ItrAdapter(
    templates_dir=templates, mappings_path=mappings, palette_cache_dir=palette_entry
)
entry = adapter.render(palette_hash, templates, mappings, out)
print("OK", entry.entry_hash, sorted(p.name for p in out.rglob("*") if p.is_file()))
