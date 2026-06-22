#!/usr/bin/env python3
"""Capture real docker/podman CLI output as conformance fixtures.

Run manually to (re)generate the fixtures committed under
``tests/conformance/fixtures/``:

    uv run python tests/conformance/capture.py

The script is idempotent: it creates the minimum resources needed
(a stopped container, a volume), captures output, then cleans up.
It skips runtimes that are not installed.

Output layout:

    tests/conformance/fixtures/
    ├── docker/
    │   ├── image_inspect_alpine.json
    │   ├── image_list.ndjson
    │   ├── container_inspect.json
    │   ├── container_list.ndjson
    │   ├── volume_inspect.json
    │   ├── volume_list.ndjson
    │   ├── network_inspect_bridge.json
    │   ├── network_list.ndjson
    │   └── pull_alpine.txt
    └── podman/
        └── ...

Each file contains the raw bytes the CLI emitted, so parser tests
run against ground truth, not the implementer's imagination.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_FIXTURES_ROOT = Path(__file__).parent / "fixtures"

_LABEL = "oci-runtime-conformance"
_CONTAINER_NAME = "oci-runtime-conformance-ctr"
_VOLUME_NAME = "oci-runtime-conformance-vol"


def _have(binary: str) -> bool:
    return shutil.which(binary) is not None


def _run(binary: str, args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [binary, *args],
        capture_output=True,
        timeout=timeout,
    )


def _save(runtime: str, name: str, data: bytes) -> None:
    d = _FIXTURES_ROOT / runtime
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(data)
    print(f"  captured {runtime}/{name} ({len(data)} bytes)")


def _cleanup(binary: str) -> None:
    for cmd in (
        ["rm", "-f", _CONTAINER_NAME],
        ["volume", "rm", "-f", _VOLUME_NAME],
    ):
        try:
            _run(binary, cmd, timeout=10)
        except Exception:
            pass


def _capture_runtime(binary: str, runtime: str) -> None:
    print(f"Capturing {runtime} fixtures...")
    _cleanup(binary)

    # --- Image inspect ---
    r = _run(binary, ["image", "inspect", "--format", "json", "alpine"])
    if r.returncode == 0:
        _save(runtime, "image_inspect_alpine.json", r.stdout)

    # --- Image list (NDJSON via --format '{{json .}}' for docker, json for podman) ---
    fmt = "{{json .}}" if runtime == "docker" else "json"
    r = _run(binary, ["image", "list", "--format", fmt])
    if r.returncode == 0:
        _save(runtime, "image_list.ndjson", r.stdout)

    # --- Pull alpine (for parse_digest_from_pull) ---
    r = _run(binary, ["pull", "alpine"], timeout=60)
    if r.returncode == 0:
        _save(runtime, "pull_alpine.txt", r.stdout)

    # --- Container: create one for inspect/list ---
    r = _run(binary, ["run", "-d", "--name", _CONTAINER_NAME, "alpine", "sleep", "300"])
    if r.returncode == 0:
        # Container inspect
        r = _run(binary, ["container", "inspect", "--format", "json", _CONTAINER_NAME])
        if r.returncode == 0:
            _save(runtime, "container_inspect.json", r.stdout)

        # Container list
        r = _run(binary, ["container", "list", "--format", fmt])
        if r.returncode == 0:
            _save(runtime, "container_list.ndjson", r.stdout)

    # --- Volume: create one for inspect/list ---
    r = _run(binary, ["volume", "create", _VOLUME_NAME])
    if r.returncode == 0:
        r = _run(binary, ["volume", "inspect", "--format", "json", _VOLUME_NAME])
        if r.returncode == 0:
            _save(runtime, "volume_inspect.json", r.stdout)

        # Volume list — docker uses '{{json .}}', podman uses 'json'
        r = _run(binary, ["volume", "list", "--format", fmt])
        if r.returncode == 0:
            _save(runtime, "volume_list.ndjson", r.stdout)

    # --- Network: bridge always exists ---
    r = _run(binary, ["network", "inspect", "--format", "json", "bridge"])
    if r.returncode == 0:
        _save(runtime, "network_inspect_bridge.json", r.stdout)

    r = _run(binary, ["network", "list", "--format", fmt])
    if r.returncode == 0:
        _save(runtime, "network_list.ndjson", r.stdout)

    _cleanup(binary)
    print(f"  {runtime} done.")


def main() -> int:
    captured_any = False
    for binary, runtime in (("docker", "docker"), ("podman", "podman")):
        if not _have(binary):
            print(f"Skipping {runtime}: not installed.")
            continue
        captured_any = True
        try:
            _capture_runtime(binary, runtime)
        except Exception as e:
            print(f"  ERROR capturing {runtime}: {e}", file=sys.stderr)
            _cleanup(binary)
    if not captured_any:
        print("No runtimes available. Install docker or podman to capture fixtures.", file=sys.stderr)
        return 1
    print("Fixtures captured. Commit them to anchor parser tests to real CLI output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
