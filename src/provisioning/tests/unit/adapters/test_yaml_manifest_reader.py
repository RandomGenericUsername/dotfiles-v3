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

    def test_duplicate_keys_raise(self, tmp_path: Path) -> None:
        path = tmp_path / "dup-keys.yaml"
        path.write_text(
            "kind: packages\nentries:\n  - name: hyprland\n    name: waybar\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match="duplicate"):
            READER.read(path)

    def test_unknown_top_level_key_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "unknown-top.yaml"
        path.write_text("kind: packages\nentries: []\nfoo: bar\n", encoding="utf-8")
        with pytest.raises(ManifestReadError, match="foo"):
            READER.read(path)

    def test_unknown_entry_key_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "unknown-entry.yaml"
        path.write_text(
            "kind: packages\nentries:\n  - name: hyprland\n    versoin: '0.1'\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match="versoin"):
            READER.read(path)

    def test_whitespace_only_kind_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "blank-kind.yaml"
        path.write_text("kind: '   '\nentries: []\n", encoding="utf-8")
        with pytest.raises(ManifestReadError, match="kind"):
            READER.read(path)

    def test_whitespace_only_name_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "blank-name.yaml"
        path.write_text("kind: packages\nentries:\n  - name: '   '\n", encoding="utf-8")
        with pytest.raises(ManifestReadError, match="name"):
            READER.read(path)

    def test_empty_string_version_becomes_none(self, tmp_path: Path) -> None:
        path = tmp_path / "empty-version.yaml"
        path.write_text(
            'kind: packages\nentries:\n  - name: hyprland\n    version: ""\n',
            encoding="utf-8",
        )
        manifest = READER.read(path)
        assert manifest.entries == (Spec(name="hyprland"),)

    def test_non_utf8_raises_manifest_read_error(self, tmp_path: Path) -> None:
        path = tmp_path / "latin1.yaml"
        path.write_bytes(b"kind: packages\nentries:\n  - name: caf\xe9\n")
        with pytest.raises(ManifestReadError, match="UTF-8"):
            READER.read(path)
