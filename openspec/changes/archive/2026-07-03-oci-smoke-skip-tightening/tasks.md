## 1. Tighten skip

- [ ] 1.1 In `tests/smoke/test_oci_integration.py`, replace `subprocess.run(["oci", "--help"], ...)` skip condition with `subprocess.run([oci_bin, "--help"], ...)` using the fixture.
- [ ] 1.2 Verify: run with `OCI_PATH=podman` — skips only if podman unavailable; runs if podman installed.