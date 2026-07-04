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
    │   ├── container_list_ports.ndjson    # container ls with published port 8080:80/tcp
    │   ├── volume_inspect.json
    │   ├── volume_list.ndjson
    │   ├── network_inspect_bridge.json
    │   ├── network_list.ndjson
    │   ├── pull_alpine.txt
    │   ├── build_output.txt               # docker build -t conformance -
    │   └── image_prune.txt                # docker image prune --force
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
_CONTAINER_NAME_PORTS = "oci-runtime-conformance-ports"
_VOLUME_NAME = "oci-runtime-conformance-vol"
_PRUNE_IMAGE_TAG = "oci-runtime-conformance-prune"


def _have(binary: str) -> bool:
    return shutil.which(binary) is not None


def _run(
    binary: str, args: list[str], *, timeout: int = 30, input_data: bytes | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [binary, *args],
        capture_output=True,
        timeout=timeout,
        input=input_data,
    )


def _save(runtime: str, name: str, data: bytes) -> None:
    d = _FIXTURES_ROOT / runtime
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(data)
    print(f"  captured {runtime}/{name} ({len(data)} bytes)")


def _cleanup(binary: str) -> None:
    for cmd in (
        ["rm", "-f", _CONTAINER_NAME],
        ["rm", "-f", _CONTAINER_NAME_PORTS],
        ["volume", "rm", "-f", _VOLUME_NAME],
        ["rmi", "-f", _PRUNE_IMAGE_TAG],
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

    # --- Network: bridge always exists for docker, podman uses 'podman' ---
    for net_name in ("bridge", "podman"):
        r = _run(binary, ["network", "inspect", "--format", "json", net_name])
        if r.returncode == 0:
            _save(runtime, f"network_inspect_{net_name}.json", r.stdout)

    r = _run(binary, ["network", "list", "--format", fmt])
    if r.returncode == 0:
        _save(runtime, "network_list.ndjson", r.stdout)

    # --- Container with published port: for port parsing conformance ---
    r = _run(
        binary,
        [
            "run",
            "-d",
            "--name",
            _CONTAINER_NAME_PORTS,
            "-p",
            "8080:80/tcp",
            "alpine",
            "sleep",
            "300",
        ],
    )
    if r.returncode == 0:
        r = _run(binary, ["container", "list", "--format", fmt])
        if r.returncode == 0:
            _save(runtime, "container_list_ports.ndjson", r.stdout)

    # --- Build output (for parse_build_output conformance) ---
    r = _run(
        binary,
        ["build", "-t", "conformance", "--quiet", "-"],
        timeout=60,
        input_data=b"FROM alpine\nRUN echo hello",
    )
    if r.returncode == 0:
        _save(runtime, "build_output.txt", r.stdout)

    # --- Image prune output (for parse_prune conformance) ---
    r = _run(
        binary,
        ["build", "--no-cache", "-t", _PRUNE_IMAGE_TAG, "-"],
        timeout=120,
        input_data=b"FROM alpine\nRUN echo unique-prune-layer",
    )
    if r.returncode == 0:
        _run(binary, ["rmi", _PRUNE_IMAGE_TAG], timeout=30)
        r = _run(binary, ["image", "prune", "--force", "--all"], timeout=60)
        if r.returncode == 0 and r.stdout.strip():
            _save(runtime, "image_prune.txt", r.stdout)
        else:
            r = _run(binary, ["system", "prune", "--force", "--all"], timeout=60)
            if r.returncode == 0 and r.stdout.strip():
                _save(runtime, "image_prune.txt", r.stdout)

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
        print(
            "No runtimes available. Install docker or podman to capture fixtures.",
            file=sys.stderr,
        )
        return 1
    print("Fixtures captured. Commit them to anchor parser tests to real CLI output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
