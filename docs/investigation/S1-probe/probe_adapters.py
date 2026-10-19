"""Run all three adapters against the recording fake CLI.

Usage (from src/runtime):
    cp ../../docs/investigation/S1-probe/fake_cli.py /tmp/opencode/fake_cli.py
    chmod +x /tmp/opencode/fake_cli.py
    FAKE_CLI_LOG=/tmp/opencode/fake_cli_log.jsonl \
        uv run python ../../docs/investigation/S1-probe/probe_adapters.py

The script writes its working artifacts under /tmp/opencode/probe.
"""

from pathlib import Path

from runtime.adapters.csg_adapter import CsgAdapter
from runtime.adapters.hashing import (
    canonical_hash_dir,
    effects_entry_hash,
    hash_file,
    icons_entry_hash,
    palette_entry_hash,
)
from runtime.adapters.itr_adapter import ItrAdapter
from runtime.adapters.weg_adapter import WegAdapter

root = Path("/tmp/opencode/probe")
root.mkdir(parents=True, exist_ok=True)
wall = root / "wallpaper.png"
wall.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 32)

templates = root / "templates"
templates.mkdir(exist_ok=True)
(templates / "colors.yaml.j2").write_text("bg: {{ bg }}\n")
mappings = root / "icons.yaml"
mappings.write_text("battery:\n  variants: []\n")
catalog = root / "effects.yaml"
catalog.write_text("effects: []\n")
colors = root / "palette-entry"
colors.mkdir(exist_ok=True)
(colors / "colors.yaml").write_text("special:\n  background: '#000000'\n")

fake = "/tmp/opencode/fake_cli.py"

wh = hash_file(wall)
th = canonical_hash_dir(templates)
ph = palette_entry_hash(wh, th)
csg_out = root / "cache" / "palettes" / ph
CsgAdapter(csg_bin=fake, templates_dir=templates).generate(wall, csg_out)

ch = hash_file(catalog)
eh = effects_entry_hash(wh, ch)
weg_out = root / "cache" / "effects" / eh
WegAdapter(weg_bin=fake, catalog_path=catalog).generate(wall, weg_out)

mh = hash_file(mappings)
ih = icons_entry_hash(ph, th, mh)
itr_out = root / "cache" / "icons" / ih
ItrAdapter(itr_bin=fake, palette_cache_dir=colors).render(ph, templates, mappings, itr_out)
print("OK")
