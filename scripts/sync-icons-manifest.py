#!/usr/bin/env python3
"""Sync icon-variant groups from icons.yaml into the AGS icons.json manifest.

WHY THIS EXISTS
---------------
`icons.json` is what the AGS icon registry reads at runtime, and nothing in the
toolchain writes it:

  MEASURED 2026-10-05: `dotfiles-runtime icons regenerate` re-renders every
  SVG into ~/.local/state/dotfiles/current/icons/ and repoints symlinks, but
  does not touch icons.json. `dotfiles-runtime reconcile` does not either.

So the manifest is maintained by hand, and a group added to icons.yaml renders
to disk perfectly while remaining invisible to the app -- the registry looks up
`group -> variant -> output` and finds no group, so the widget resolves to null
and renders nothing. That is the same "implemented but invisible" failure that
produced a dead Bluetooth agent, a dead confirm button and a dead chevron.

This script closes the gap by deriving the manifest's group entries from the
mapping file, which is the actual source of truth.

It is ADDITIVE BY DESIGN and preserves everything it does not own:

  - groups named on the command line are replaced wholesale;
  - every other group is copied through byte-for-byte, so hand-tuned entries
    (notably `settings-panel`, which the audio-panel deploy modifies) survive;
  - output formatting matches the generator exactly (json.dump indent=2,
    sort_keys=True), verified by round-tripping the file unchanged first.

Usage:
    python3 scripts/sync-icons-manifest.py spinner-ring spinner-dots ...
    python3 scripts/sync-icons-manifest.py --list
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

REPO = pathlib.Path(__file__).resolve().parent.parent
SPINE = pathlib.Path.home() / ".local/share/dotfiles"
YAML_PATH = SPINE / "icon-mappings" / "icons.yaml"
JSON_PATH = SPINE / "config" / "ags" / "icons.json"

# Keys the manifest carries per group, in the shape the registry expects.
CARRY = ("variants", "color_mappings", "bar_mappings")


def group_entry(name: str, spec: dict) -> dict:
    """Build one manifest entry, keeping only the keys the registry uses."""
    entry: dict = {}
    for key in CARRY:
        if key in spec and spec[key] is not None:
            entry[key] = spec[key]
    if "variants" not in entry:
        raise SystemExit(f"group {name!r} has no variants; refusing to write it")
    for v in entry["variants"]:
        missing = [k for k in ("name", "output", "template") if k not in v]
        if missing:
            raise SystemExit(
                f"group {name!r} variant {v.get('name')!r} missing {missing}"
            )
    return entry


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("groups", nargs="*", help="group names to sync")
    ap.add_argument("--list", action="store_true", help="list groups in icons.yaml")
    ap.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=JSON_PATH,
        help="icons.json to update (default: the deployed spine manifest)",
    )
    ap.add_argument(
        "--yaml",
        type=pathlib.Path,
        default=YAML_PATH,
        help="mapping file to read (default: the deployed spine mappings)",
    )
    args = ap.parse_args()

    yaml_path = args.yaml
    json_path = args.manifest
    spec = yaml.safe_load(yaml_path.read_text()) or {}
    if args.list:
        for name in sorted(spec):
            n = len(spec[name].get("variants", []) or [])
            print(f"  {name:28s} {n} variant(s)")
        return 0

    if not args.groups:
        print("nothing to do: pass group names, or --list", file=sys.stderr)
        return 2

    unknown = [g for g in args.groups if g not in spec]
    if unknown:
        print(f"not in {YAML_PATH}: {', '.join(unknown)}", file=sys.stderr)
        return 2

    manifest = json.loads(json_path.read_text())

    # Formatting guard: if we cannot reproduce the file byte-for-byte from its
    # own contents, we must not rewrite it, because a whole-file reformat would
    # bury a real change in thousands of lines of noise.
    round_trip = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if round_trip != json_path.read_text():
        print(
            "REFUSING to write: re-serialising the manifest does not reproduce "
            "the file byte-for-byte, so this script does not yet match the "
            "generator's formatting.",
            file=sys.stderr,
        )
        return 1

    for name in args.groups:
        before = manifest.get(name)
        manifest[name] = group_entry(name, spec[name])
        n = len(manifest[name]["variants"])
        state = "replaced" if before else "added"
        print(f"  {state} {name} ({n} variants)")

    json_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"{json_path} now has {len(manifest)} groups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())