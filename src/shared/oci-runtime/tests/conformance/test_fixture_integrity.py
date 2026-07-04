from pathlib import Path

_FIXTURE_DIR = Path(__file__).parent / "fixtures"

REQUIRED_FIXTURES = [
    "README.txt",
    "docker/build_output.txt",
    "docker/container_inspect.json",
    "docker/container_list_ports.ndjson",
    "docker/container_list.ndjson",
    "docker/image_inspect_alpine.json",
    "docker/image_list.ndjson",
    "docker/image_prune.txt",
    "docker/network_inspect_bridge.json",
    "docker/network_list.ndjson",
    "docker/pull_alpine.txt",
    "docker/volume_inspect.json",
    "docker/volume_list.ndjson",
    "podman/build_output.txt",
    "podman/container_inspect.json",
    "podman/container_list_ports.ndjson",
    "podman/container_list.ndjson",
    "podman/image_inspect_alpine.json",
    "podman/image_list.ndjson",
    "podman/image_prune.txt",
    "podman/network_inspect_podman.json",
    "podman/network_list.ndjson",
    "podman/pull_alpine.txt",
    "podman/volume_inspect.json",
    "podman/volume_list.ndjson",
]


class TestFixtureIntegrity:
    def test_all_required_fixtures_present(self):
        missing = []
        for rel in REQUIRED_FIXTURES:
            p = _FIXTURE_DIR / rel
            if not p.is_file():
                missing.append(rel)
        assert not missing, f"Missing fixture file(s): {missing}"

    def test_no_author_specific_paths_in_fixtures(self):
        hits: list[str] = []
        for pattern in ("*.json", "*.txt", "*.ndjson"):
            for p in sorted(_FIXTURE_DIR.rglob(pattern)):
                if p.is_file():
                    text = p.read_text(encoding="utf-8", errors="replace")
                    if "/home/" in text:
                        rel = p.relative_to(_FIXTURE_DIR)
                        hits.append(str(rel))
        assert not hits, (
            f"Fixture file(s) contain /home/ paths (likely author-specific): {hits}"
        )
