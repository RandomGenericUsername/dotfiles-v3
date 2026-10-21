from __future__ import annotations

from pathlib import Path

import pytest

from provisioning.adapters.yaml_manifest_reader import ManifestReadError, YamlManifestReader
from provisioning.domain.enums import ManifestKind
from provisioning.domain.models import ProvisionManifest, Spec

READER = YamlManifestReader()


def _find_manifest_dir() -> Path:
    """Locate the real manifests dir by walking up from this test file.

    Resolves the repo root robustly (no fixed-depth assumption) and fails
    loudly if the manifests are missing, so AC 7/8 coverage can never
    silently disappear from the run.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "dotfiles" / "provisioning"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "dotfiles/provisioning/ not found walking up from the test file; "
        "AC 7/8 real-manifest coverage requires the authored manifests"
    )


_MANIFEST_DIR = _find_manifest_dir()


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
            kind=ManifestKind.PACKAGES,
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


class TestYamlManifestReaderPerKindSchemas:
    def test_returns_manifest_kind_enum(self, tmp_path: Path) -> None:
        path = tmp_path / "packages.yaml"
        path.write_text("kind: packages\nentries:\n  - name: hyprland\n", encoding="utf-8")
        manifest = READER.read(path)
        assert manifest.kind is ManifestKind.PACKAGES

    def test_unknown_kind_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "unknown-kind.yaml"
        path.write_text("kind: mysterio\nentries: []\n", encoding="utf-8")
        with pytest.raises(ManifestReadError, match="kind"):
            READER.read(path)

    def test_unknown_kind_error_names_supported_set(self, tmp_path: Path) -> None:
        path = tmp_path / "unknown-kind.yaml"
        path.write_text("kind: mysterio\nentries: []\n", encoding="utf-8")
        with pytest.raises(ManifestReadError, match="cli-tools") as excinfo:
            READER.read(path)
        assert "mysterio" in str(excinfo.value)

    def test_assets_kind_entry_allows_rich_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "assets.yaml"
        path.write_text(
            "kind: assets\n"
            "entries:\n"
            "  - name: wallpapers\n"
            "    kind: wallpaper\n"
            "    source: \"{{ install_dir | trim }}/assets/v0.2.0/content/wallpapers/wallpapers.tar.gz\"\n"
            "  - name: battery\n"
            "    kind: icon-mapping\n"
            "    source: \"{{ install_dir | trim }}/assets/v0.2.0/icons/mappings/\"\n",
            encoding="utf-8",
        )
        manifest = READER.read(path)
        assert manifest.kind is ManifestKind.ASSETS
        assert manifest.entries == (Spec(name="wallpapers"), Spec(name="battery"))

    def test_assets_kind_missing_required_kind_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "assets.yaml"
        path.write_text(
            "kind: assets\nentries:\n  - name: wallpapers\n    source: x\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match="kind"):
            READER.read(path)

    def test_assets_kind_invalid_assetkind_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "assets.yaml"
        path.write_text(
            "kind: assets\nentries:\n  - name: x\n    kind: not-an-asset-kind\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match="AssetKind"):
            READER.read(path)

    def test_assets_kind_unknown_entry_key_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "assets.yaml"
        path.write_text(
            "kind: assets\nentries:\n  - name: x\n    kind: wallpaper\n    bogus: y\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match="bogus"):
            READER.read(path)

    def test_assets_kind_accepts_the_pin_block(self, tmp_path: Path) -> None:
        """AD-6: `assets: {repo, tag, classes}` is valid on the assets manifest
        and is deliberately NOT captured into the domain view."""
        path = tmp_path / "assets.yaml"
        path.write_text(
            "kind: assets\n"
            "assets:\n"
            "  repo: https://github.com/RandomGenericUsername/dotfiles-assets\n"
            "  tag: v0.2.0\n"
            "  classes:\n"
            "    icons: { dest: icons, schema: icons/schema.json }\n"
            "    templates: { dest: templates, schema: '**/vars.schema.json' }\n"
            "    configs: { dest: configs, schema: null }\n"
            "    content: { dest: content, schema: null }\n"
            "    desktop: { dest: desktop, schema: desktop/desktop.yaml }\n"
            "entries:\n"
            "  - name: wallpapers\n    kind: wallpaper\n    source: x\n",
            encoding="utf-8",
        )
        manifest = READER.read(path)
        assert manifest.kind is ManifestKind.ASSETS
        assert manifest.entries == (Spec(name="wallpapers"),)

    @pytest.mark.parametrize(
        ("block", "match"),
        [
            ("assets:\n  repo: nope\n  tag: v0.2.0\n  classes: {}\n", "assets.repo"),
            ("assets:\n  repo: https://x/y\n  tag: latest\n  classes: {}\n", "assets.tag"),
            ("assets:\n  repo: https://x/y\n  tag: v0.2.0\n  classes: {}\n", "classes"),
            (
                "assets:\n  repo: https://x/y\n  tag: v0.2.0\n  bogus: 1\n"
                "  classes: {}\n",
                "unknown keys",
            ),
        ],
    )
    def test_assets_kind_invalid_pin_block_rejected(
        self, tmp_path: Path, block: str, match: str
    ) -> None:
        path = tmp_path / "assets.yaml"
        path.write_text(
            "kind: assets\n" + block + "entries: []\n", encoding="utf-8"
        )
        with pytest.raises(ManifestReadError, match=match):
            READER.read(path)

    def test_pin_block_rejected_on_other_kinds(self, tmp_path: Path) -> None:
        path = tmp_path / "packages.yaml"
        path.write_text(
            "kind: packages\nassets:\n  repo: https://x/y\n  tag: v0.2.0\n"
            "  classes: {}\nentries: []\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match="unknown keys"):
            READER.read(path)

    def test_config_copies_kind_requires_target(self, tmp_path: Path) -> None:
        path = tmp_path / "config-copies.yaml"
        path.write_text("kind: config-copies\nentries:\n  - name: nvim\n", encoding="utf-8")
        with pytest.raises(ManifestReadError, match="target"):
            READER.read(path)

    def test_config_copies_kind_parses_target(self, tmp_path: Path) -> None:
        path = tmp_path / "config-copies.yaml"
        path.write_text(
            "kind: config-copies\nentries:\n  - name: nvim\n    target: nvim\n",
            encoding="utf-8",
        )
        manifest = READER.read(path)
        assert manifest.kind is ManifestKind.CONFIG_COPIES
        assert manifest.entries == (Spec(name="nvim"),)

    @pytest.mark.parametrize("bad_target", ["", "   ", "42", "null"])
    def test_config_copies_kind_empty_target_rejected(
        self, tmp_path: Path, bad_target: str
    ) -> None:
        path = tmp_path / "config-copies.yaml"
        path.write_text(
            f"kind: config-copies\nentries:\n  - name: nvim\n    target: {bad_target}\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match="target"):
            READER.read(path)

    def test_cli_tools_kind_requires_source_or_repo_and_tag(self, tmp_path: Path) -> None:
        path = tmp_path / "cli-tools.yaml"
        path.write_text("kind: cli-tools\nentries:\n  - name: csg\n", encoding="utf-8")
        with pytest.raises(ManifestReadError, match="source"):
            READER.read(path)

    def test_cli_tools_kind_parses_source(self, tmp_path: Path) -> None:
        path = tmp_path / "cli-tools.yaml"
        path.write_text(
            "kind: cli-tools\n"
            "entries:\n"
            "  - name: csg\n"
            "    source: src/cli-tools/color-scheme-generator\n",
            encoding="utf-8",
        )
        manifest = READER.read(path)
        assert manifest.kind is ManifestKind.CLI_TOOLS
        assert manifest.entries == (Spec(name="csg"),)

    def test_cli_tools_kind_parses_repo_and_tag(self, tmp_path: Path) -> None:
        """The pinned shape (spine AD-10): {name, repo, tag} with no source."""
        path = tmp_path / "cli-tools.yaml"
        path.write_text(
            "kind: cli-tools\n"
            "entries:\n"
            "  - name: itr\n"
            "    repo: https://github.com/RandomGenericUsername/icon-templates-renderer\n"
            "    tag: v0.1.0\n",
            encoding="utf-8",
        )
        manifest = READER.read(path)
        assert manifest.kind is ManifestKind.CLI_TOOLS
        assert manifest.entries == (Spec(name="itr"),)

    def test_cli_tools_kind_parses_mixed_shapes(self, tmp_path: Path) -> None:
        """The extraction window carries both shapes at once (source XOR repo+tag)."""
        path = tmp_path / "cli-tools.yaml"
        path.write_text(
            "kind: cli-tools\n"
            "entries:\n"
            "  - name: csg\n"
            "    source: src/cli-tools/color-scheme-generator\n"
            "  - name: itr\n"
            "    repo: https://github.com/RandomGenericUsername/icon-templates-renderer\n"
            "    tag: v0.1.0\n",
            encoding="utf-8",
        )
        manifest = READER.read(path)
        assert manifest.entries == (Spec(name="csg"), Spec(name="itr"))

    @pytest.mark.parametrize("missing", ["repo", "tag"])
    def test_cli_tools_kind_rejects_incomplete_pin(
        self, tmp_path: Path, missing: str
    ) -> None:
        fields = {"repo": "https://example.invalid/repo", "tag": "v0.1.0"}
        del fields[missing]
        body = "".join(f"    {key}: {value}\n" for key, value in fields.items())
        path = tmp_path / "cli-tools.yaml"
        path.write_text(
            f"kind: cli-tools\nentries:\n  - name: itr\n{body}", encoding="utf-8"
        )
        with pytest.raises(ManifestReadError, match="repo.*tag|source"):
            READER.read(path)

    def test_cli_tools_kind_rejects_both_shapes(self, tmp_path: Path) -> None:
        path = tmp_path / "cli-tools.yaml"
        path.write_text(
            "kind: cli-tools\n"
            "entries:\n"
            "  - name: itr\n"
            "    source: src/cli-tools/icon-templates-renderer\n"
            "    repo: https://example.invalid/repo\n"
            "    tag: v0.1.0\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match="both"):
            READER.read(path)

    @pytest.mark.parametrize("rich_key", ["repo", "tag"])
    def test_cli_tools_kind_empty_pin_field_rejected(
        self, tmp_path: Path, rich_key: str
    ) -> None:
        fields = {"repo": "https://example.invalid/repo", "tag": "v0.1.0"}
        fields[rich_key] = "'   '"
        body = "".join(f"    {key}: {value}\n" for key, value in fields.items())
        path = tmp_path / "cli-tools.yaml"
        path.write_text(
            f"kind: cli-tools\nentries:\n  - name: itr\n{body}", encoding="utf-8"
        )
        with pytest.raises(ManifestReadError, match=rich_key):
            READER.read(path)

    @pytest.mark.parametrize("bad_source", ["", "   ", "42"])
    def test_cli_tools_kind_empty_source_rejected(self, tmp_path: Path, bad_source: str) -> None:
        path = tmp_path / "cli-tools.yaml"
        path.write_text(
            f"kind: cli-tools\nentries:\n  - name: csg\n    source: {bad_source}\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match="source"):
            READER.read(path)

    def test_assets_kind_empty_source_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "assets.yaml"
        path.write_text(
            "kind: assets\nentries:\n  - name: wallpapers\n    kind: wallpaper\n    source: ''\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match="source"):
            READER.read(path)

    def test_filesystem_kind_allows_only_name(self, tmp_path: Path) -> None:
        path = tmp_path / "filesystem.yaml"
        path.write_text(
            "kind: filesystem\nentries:\n  - name: wallpapers\n  - name: generated/icons\n",
            encoding="utf-8",
        )
        manifest = READER.read(path)
        assert manifest.kind is ManifestKind.FILESYSTEM
        assert manifest.entries == (Spec(name="wallpapers"), Spec(name="generated/icons"))

    def test_filesystem_kind_unknown_key_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "filesystem.yaml"
        path.write_text(
            "kind: filesystem\nentries:\n  - name: wallpapers\n    target: x\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match="target"):
            READER.read(path)

    def test_packages_kind_rich_key_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "packages.yaml"
        path.write_text(
            "kind: packages\nentries:\n  - name: hyprland\n    source: x\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestReadError, match="source"):
            READER.read(path)


class TestReadRealManifests:
    """AC 7/8: every authored manifest parses into a non-empty ProvisionManifest."""

    @pytest.mark.parametrize(
        ("filename", "expected_kind"),
        [
            ("packages.yaml", ManifestKind.PACKAGES),
            ("assets.yaml", ManifestKind.ASSETS),
            ("filesystem.yaml", ManifestKind.FILESYSTEM),
            ("config-copies.yaml", ManifestKind.CONFIG_COPIES),
            ("cli-tools.yaml", ManifestKind.CLI_TOOLS),
        ],
    )
    def test_parses_real_manifest(self, filename: str, expected_kind: ManifestKind) -> None:
        manifest = READER.read(_MANIFEST_DIR / filename)
        assert manifest.kind is expected_kind
        assert manifest.entries, f"{filename} must not be empty"

    def test_packages_manifest_has_verified_set(self) -> None:
        manifest = READER.read(_MANIFEST_DIR / "packages.yaml")
        names = [entry.name for entry in manifest.entries]
        # Strip trailing inline comments — the manifest annotates entries.
        names = [name.split("#")[0].strip() for name in names]
        assert len(names) == len(set(names)), f"duplicate package entries: {names}"
        # Drift lock, re-snapshotted 2026-10-04 by openspec change
        # repair-package-manifest-drift after a per-key `git log -S<key>`
        # review (per-key table in that change's design.md):
        #   libva-utils        e9beedc4 — VA-API codec probe (vainfo)
        #   nm-connection-editor / speedtest  predate this snapshot (bulk AGS
        #                       import 496a0b4d); both are installed by
        #                       group_vars and consumed by the AGS Wi-Fi
        #                       settings footer / speedtest service
        # They were present in the MANIFEST and missing from THIS expectation,
        # which is why the data needed no edit — only the lock did.
        #
        # Re-snapshotted 2026-10-04 by openspec change
        # harden-verify-probes-and-manifest, which resolved the three
        # orphans repair-package-manifest-drift had found (evidence table in
        # that change's design.md):
        #   lf          REMOVED from packages.yaml — no consumer anywhere
        #               (no keybind, autostart, desktop file, config, spec).
        #   hyprcursor  REMOVED from packages.yaml — no consumer, and already
        #               a direct pacman dependency of hyprland, so it arrives
        #               transitively; declaring it separately implied a
        #               consumer that does not exist.
        #   xdg-utils   RETAINED in the manifest and ADDED to both group_vars
        #               maps — it has hard consumers (gui_tools `xdg-mime
        #               default`, verify `xdg-mime query default`, capture-tool
        #               and hypr-pano `xdg-open`), so removing it would have
        #               broken a real path.
        assert set(names) == {
            "hyprland",
            "hyprpaper",
            "ags",
            "astal-hyprland",
            "astal-battery",
            "astal-network",
            "networkmanager",
            "wifitui",
            "uwsm",
            "fonts",
            "librsvg",
            "dunst",
            "hyprpolkitagent",
            "xdg-desktop-portal-hyprland",
            "xdg-desktop-portal-gtk",
            "xdg-utils",
            "wl-clipboard",
            "grim",
            "slurp",
            "ffmpeg",
            "pipewire",
            "wireplumber",
            "pipewire-audio",
            "pipewire-pulse",
            "pavucontrol",
            "gpu-screen-recorder",
            "wf-recorder",
            "libva-utils",
            "rofi",
            "thunar",
            "btop",
            "thunderbird",
            "tidal-hifi",
            "brightnessctl",
            "playerctl",
            "power-options-gtk",
            "hyprmod",
            "hyprlock",
            "hypridle",
            "wlogout",
            "astal-wp",
            "bluez",
            "bluez-utils",
            "blueman",
            "nm-connection-editor",
            "speedtest",
            # AI development tools (provision-ai-ides-and-clis) — Arch-only AUR
            # (windsurf -> devin-desktop, vscode -> visual-studio-code-bin).
            "antigravity-ide",
            "windsurf",
            "vscode",
            "copilot-cli",
            "codex-cli",
        }

    def test_config_copies_manifest_lists_only_existing_dirs(self) -> None:
        manifest = READER.read(_MANIFEST_DIR / "config-copies.yaml")
        names = [entry.name for entry in manifest.entries]
        assert len(names) == len(set(names)), f"duplicate config-copy entries: {names}"
        assert set(names) == {"nvim", "starship", "wlogout", "zsh"}
        assert "hypr" not in names
        assert "hyprpaper" not in names
        assert "ags" not in names

    def test_cli_tools_manifest_has_four_install_targets(self) -> None:
        manifest = READER.read(_MANIFEST_DIR / "cli-tools.yaml")
        names = [entry.name for entry in manifest.entries]
        assert len(names) == len(set(names)), f"duplicate cli-tool entries: {names}"
        assert set(names) == {"csg", "weg", "itr", "dotfiles-runtime"}
