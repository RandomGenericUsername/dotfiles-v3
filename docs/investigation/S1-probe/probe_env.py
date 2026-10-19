"""Probe which host env keys build_env forwards to the CLI subprocess.

Usage (from src/runtime):
    COLORSCHEME_TEMPLATES_TEMPLATES_DIR=/tmp/x \
    WALLPAPER_EFFECTS_CONFIG_FILE_PATH=/tmp/z \
    ICON_RENDERER_CONFIG_FILE_PATH=/tmp/w \
    MY_SECRET_TOKEN=leak XDG_CONFIG_HOME=/tmp/xdg-config \
    FAKE_CLI_LOG=/tmp/opencode/fake_cli_log.jsonl \
        uv run python ../../docs/investigation/S1-probe/probe_env.py
"""

from pathlib import Path

from runtime.adapters.csg_adapter import CsgAdapter
from runtime.adapters.hashing import canonical_hash_dir, hash_file, palette_entry_hash

root = Path("/tmp/opencode/probe_env")
root.mkdir(parents=True, exist_ok=True)
wall = root / "wallpaper.png"
wall.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 32)
templates = root / "templates"
templates.mkdir(exist_ok=True)
(templates / "colors.yaml.j2").write_text("bg: {{ bg }}\n")
ph = palette_entry_hash(hash_file(wall), canonical_hash_dir(templates))
CsgAdapter(csg_bin="/tmp/opencode/fake_cli.py", templates_dir=templates).generate(
    wall, root / "cache" / "palettes" / ph
)
print("OK")
