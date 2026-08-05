from __future__ import annotations

from pathlib import Path

import pytest

from provisioning.adapters.yaml_manifest_reader import ManifestReadError, YamlManifestReader
from provisioning.domain.models import ProvisionManifest, Spec

READER = YamlManifestReader()


class TestYamlManifestReader:
    def test_reads_kind_and_entries(self, tmp_path: Path) -> None:
        path = tmp_path / "packages.yaml"
        path.write_text(
            "kind: packages\n"
            "entries:\n"
            "  - name: hyprland\n"
            '    version: "0.40.2"\n'
            "  - name: waybar\n",
            encoding="utf-8",
        )
        manifest = READER.read(path)
        assert manifest == ProvisionManifest(
            kind="packages",
            entries=(Spec(name="hyprland", version="0.40.2"), Spec(name="waybar")),
        )

    def test_version_null_becomes_none(self, tmp_path: Path) -> None:
        path = tmp_path / "packages.yaml"
        path.write_text(
            "kind: packages\nentries:\n  - name: hyprland\n    version: null\n",
            encoding="utf-8",
        )
        manifest = READER.read(path)
        assert manifest.entries == (Spec(name="hyprland"),)

    def test_empty_entries_produces_empty_tuple(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.yaml"
        path.write_text("kind: packages\nentries: []\n", encoding="utf-8")
        assert READER.read(path).entries == ()

    def test_malformed_yaml_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.yaml"
        path.write_text(
            "kind: packages\nentries:\n  - name: [unclosed\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match=str(path)):
            READER.read(path)

    def test_missing_kind_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "missing-kind.yaml"
        path.write_text("entries: []\n", encoding="utf-8")
        with pytest.raises(ManifestReadError, match="kind"):
            READER.read(path)

    def test_missing_entries_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "missing-entries.yaml"
        path.write_text("kind: packages\n", encoding="utf-8")
        with pytest.raises(ManifestReadError, match="entries"):
            READER.read(path)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ManifestReadError):
            READER.read(tmp_path / "does-not-exist.yaml")

    def test_malformed_entry_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad-entry.yaml"
        path.write_text(
            'kind: packages\nentries:\n  - version: "0.1"\n',
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match="name"):
            READER.read(path)
