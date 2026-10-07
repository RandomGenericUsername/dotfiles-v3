#!/usr/bin/env python3
"""icons.json == to_nice_json(icons.yaml) drift gate.

`dotfiles/config/ags/icons.json` is GENERATED OUTPUT, not a source. It is
written by the `compositor_configs` role with exactly this expression
(`roles/compositor_configs/tasks/main.yml:88,96`):

    {{ (compositor_configs_icon_manifest.content | b64decode | from_yaml)
       | to_nice_json(indent=2) }}

...appended with a trailing newline. Nothing asserted that relationship, so the
committed projection could rot silently in either direction: a hand edit that
provisioning overwrites at the next bootstrap, or -- what actually happened --
a change to `icons.yaml` that was never regenerated, leaving `icons.json`
disagreeing with its own source forever. The committed `icons.json` had been
carrying `null` for the four `wifi-signal-*` `color_mappings` its templates
declare since commit `f161e246`, and no gate said a word.

WHY A GATE AND NOT A NOTE. The staleness was invisible precisely because it was
correctable in one command nobody was prompted to run. The durable fix is the
assertion, not the reminder: it makes the regeneration a review step (change the
YAML, the gate tells you the JSON is stale) instead of a silent divergence.

WHY IT USES ANSIBLE'S OWN FILTER rather than `json.dumps`. `to_nice_json` is
`json.dumps(a, indent=indent, sort_keys=True, separators=(',', ': '))` with
ansible's encoder layered on, and the role emits through it. Comparing against
an approximation of the generator is how a file regenerated "the same way" ends
up differing from what provisioning actually writes on the next run. So the
filter is imported and called, and if ansible is not importable the gate FAILS
with that stated -- it does not fall back to a guess and it does not skip.

Usage: ``python3 scripts/icons-json-drift.py [--root REPO_ROOT] [--update]``
Exit 0 = icons.json is exactly what the role would write.
Exit 1 = drift (with a diff), or a missing/unreadable input.

Run it through the provisioning project so ansible is importable:

    uv run --directory src/provisioning python ../../scripts/icons-json-drift.py

The `../../` is load-bearing: `--directory` moves the interpreter's CWD to
src/provisioning, so a `scripts/...` path does not resolve from there. The
script locates the repo from its own `__file__`, so its own CWD does not
matter -- only the path you type to reach it does.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

YAML_FILE = "dotfiles/config/icon-template-color-scheme-mappings/icons.yaml"
JSON_FILE = "dotfiles/config/ags/icons.json"

# The role writes `content: "{{ ... | to_nice_json(indent=2) }}\n"` -- the
# trailing newline is part of the template, not of the filter's output.
TRAILING_NEWLINE = "\n"


def render(json_text: str) -> str:
    return json_text + TRAILING_NEWLINE


def main() -> int:
    ap = argparse.ArgumentParser(description="icons.json projection drift gate")
    ap.add_argument("--root", default=None, help="repo root (default: parent of scripts/)")
    ap.add_argument(
        "--update",
        action="store_true",
        help="rewrite icons.json from the YAML and exit (the regeneration, for the "
        "author who just changed the YAML -- the gate itself never writes)",
    )
    args = ap.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    yaml_path = root / YAML_FILE
    json_path = root / JSON_FILE

    if not yaml_path.is_file():
        print(f"MISSING source manifest: {yaml_path}")
        return 1
    if not json_path.is_file() and not args.update:
        print(f"MISSING generated manifest: {json_path}")
        return 1

    # The generator's own filter, not an approximation of it (see module docstring).
    try:
        from ansible.plugins.filter.core import to_nice_json  # type: ignore[import-not-found]
    except ImportError as exc:
        print(
            f"FAIL: ansible is not importable ({exc}); this gate compares against "
            f"the role's OWN to_nice_json filter, so it must not guess at the "
            f"generator. Run it as: "
            f"uv run --directory src/provisioning python ../../scripts/icons-json-drift.py"
        )
        return 1

    import yaml  # PyYAML ships with the provisioning project (ansible-core dep)

    data = yaml.safe_load(yaml_path.read_text())
    expected = render(to_nice_json(data, indent=2))

    if args.update:
        json_path.write_text(expected)
        print(f"icons-json-drift: WROTE {JSON_FILE} from {YAML_FILE}")
        return 0

    actual = json_path.read_text()
    if actual == expected:
        print(
            f"icons-json-drift: PASS ({JSON_FILE} is exactly "
            f"to_nice_json({YAML_FILE}, indent=2))"
        )
        return 0

    diff = list(
        difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=f"{JSON_FILE} (committed)",
            tofile=f"{JSON_FILE} (regenerated from {YAML_FILE})",
        )
    )
    print(
        f"FAIL: {JSON_FILE} has DRIFTED from {YAML_FILE}.\n"
        f"  It is generated output: `compositor_configs` overwrites it with\n"
        f"  `(from_yaml) | to_nice_json(indent=2)`, so a stale projection is\n"
        f"  silently reverted at the next bootstrap -- and nothing else noticed.\n"
        f"  Regenerate with:\n"
        f"    uv run --directory src/provisioning python ../../scripts/icons-json-drift.py --update"
    )
    sys.stdout.writelines(diff)
    return 1


if __name__ == "__main__":
    sys.exit(main())