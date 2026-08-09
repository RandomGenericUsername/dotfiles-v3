from __future__ import annotations

import pytest

from provisioning.domain.enums import AssetKind, Capability, CapabilityKind, Distro, ManifestKind
from provisioning.domain.models import (
    MachineState,
    ProvisionManifest,
    ProvisionResult,
    Spec,
)


class TestDistro:
    def test_members(self) -> None:
        assert Distro.ARCH.value == "arch"
        assert Distro.DEBIAN_FAMILY.value == "debian-family"

    def test_str_returns_value(self) -> None:
        assert str(Distro.ARCH) == "arch"
        assert str(Distro.DEBIAN_FAMILY) == "debian-family"

    def test_construction_from_value(self) -> None:
        assert Distro("arch") is Distro.ARCH
        assert Distro("debian-family") is Distro.DEBIAN_FAMILY

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            Distro("fedora")


class TestCapability:
    def test_members(self) -> None:
        assert Capability.HYPRLAND.value == "Hyprland"
        assert Capability.HYPRPAPER.value == "hyprpaper"
        assert Capability.WAYBAR.value == "waybar"
        assert Capability.CSG.value == "csg"
        assert Capability.WEG.value == "weg"
        assert Capability.ICON_RENDERER.value == "itr"
        assert Capability.FONTS.value == "fonts"

    def test_kind_binary(self) -> None:
        assert Capability.HYPRLAND.kind() is CapabilityKind.BINARY
        assert Capability.HYPRPAPER.kind() is CapabilityKind.BINARY
        assert Capability.WAYBAR.kind() is CapabilityKind.BINARY
        assert Capability.CSG.kind() is CapabilityKind.BINARY
        assert Capability.WEG.kind() is CapabilityKind.BINARY
        assert Capability.ICON_RENDERER.kind() is CapabilityKind.BINARY

    def test_kind_package_group(self) -> None:
        assert Capability.FONTS.kind() is CapabilityKind.PACKAGE_GROUP


class TestManifestKind:
    def test_members(self) -> None:
        assert ManifestKind.PACKAGES.value == "packages"
        assert ManifestKind.ASSETS.value == "assets"
        assert ManifestKind.FILESYSTEM.value == "filesystem"
        assert ManifestKind.SYMLINKS.value == "symlinks"
        assert ManifestKind.CLI_TOOLS.value == "cli-tools"

    def test_str_returns_value(self) -> None:
        assert str(ManifestKind.PACKAGES) == "packages"
        assert str(ManifestKind.CLI_TOOLS) == "cli-tools"

    def test_construction_from_value(self) -> None:
        assert ManifestKind("packages") is ManifestKind.PACKAGES
        assert ManifestKind("cli-tools") is ManifestKind.CLI_TOOLS

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError):
            ManifestKind("nope")


class TestAssetKind:
    def test_members(self) -> None:
        assert AssetKind.WALLPAPER.value == "wallpaper"
        assert AssetKind.ICON_TEMPLATE.value == "icon-template"
        assert AssetKind.ICON_MAPPING.value == "icon-mapping"
        assert AssetKind.CSG_TEMPLATE.value == "csg-template"
        assert AssetKind.WEG_EFFECTS.value == "weg-effects"

    def test_spine_segment_maps_to_install_spine_paths(self) -> None:
        assert AssetKind.WALLPAPER.spine_segment() == "wallpapers"
        assert AssetKind.ICON_TEMPLATE.spine_segment() == "icon-templates"
        assert AssetKind.ICON_MAPPING.spine_segment() == "icon-mappings"
        assert AssetKind.CSG_TEMPLATE.spine_segment() == "csg-templates"
        assert AssetKind.WEG_EFFECTS.spine_segment() == "weg-effects.yaml"


class TestSpec:
    def test_constructs_with_all_fields(self) -> None:
        spec = Spec(name="hyprland", version="0.1.0")
        assert spec.name == "hyprland"
        assert spec.version == "0.1.0"

    def test_missing_required_field_rejected(self) -> None:
        with pytest.raises(TypeError):
            Spec()  # type: ignore[call-arg]

    def test_frozen(self) -> None:
        spec = Spec(name="hyprland", version="0.1.0")
        with pytest.raises(AttributeError):
            spec.name = "waybar"  # type: ignore[misc]

    def test_equality(self) -> None:
        assert Spec(name="hyprland", version="0.1.0") == Spec(name="hyprland", version="0.1.0")
        assert Spec(name="hyprland", version="0.1.0") != Spec(name="hyprland", version="0.2.0")


class TestMachineState:
    def test_constructs_with_all_fields(self) -> None:
        state = MachineState(distro=Distro.ARCH, install_dir="/home/u/.local/share/dotfiles")
        assert state.distro is Distro.ARCH
        assert state.install_dir == "/home/u/.local/share/dotfiles"

    def test_frozen(self) -> None:
        state = MachineState(distro=Distro.ARCH, install_dir="/x")
        with pytest.raises(AttributeError):
            state.install_dir = "/y"  # type: ignore[misc]

    def test_equality(self) -> None:
        assert MachineState(distro=Distro.ARCH, install_dir="/x") == MachineState(
            distro=Distro.ARCH, install_dir="/x"
        )
        assert MachineState(distro=Distro.ARCH, install_dir="/x") != MachineState(
            distro=Distro.DEBIAN_FAMILY, install_dir="/x"
        )


class TestProvisionManifest:
    def test_constructs_with_all_fields(self) -> None:
        manifest = ProvisionManifest(
            kind=ManifestKind.PACKAGES, entries=(Spec(name="hyprland", version=None),)
        )
        assert manifest.kind is ManifestKind.PACKAGES
        assert len(manifest.entries) == 1

    def test_frozen(self) -> None:
        manifest = ProvisionManifest(kind=ManifestKind.PACKAGES, entries=())
        with pytest.raises(AttributeError):
            manifest.kind = ManifestKind.ASSETS  # type: ignore[misc]

    def test_hashable(self) -> None:
        manifest = ProvisionManifest(kind=ManifestKind.PACKAGES, entries=())
        assert isinstance(hash(manifest), int)

    def test_default_entries_are_independent(self) -> None:
        manifest_a = ProvisionManifest(kind=ManifestKind.PACKAGES)
        manifest_b = ProvisionManifest(kind=ManifestKind.PACKAGES)
        assert manifest_a.entries == ()
        assert manifest_b.entries == ()
        assert hash(manifest_a) == hash(manifest_b)

    def test_equality(self) -> None:
        entries_a = (Spec(name="hyprland", version=None),)
        entries_b = (Spec(name="hyprland", version=None),)
        assert entries_a is not entries_b
        assert ProvisionManifest(
            kind=ManifestKind.PACKAGES, entries=entries_a
        ) == ProvisionManifest(kind=ManifestKind.PACKAGES, entries=entries_b)
        assert ProvisionManifest(
            kind=ManifestKind.PACKAGES, entries=entries_a
        ) != ProvisionManifest(kind=ManifestKind.ASSETS, entries=entries_a)


class TestProvisionResult:
    def test_constructs_with_all_fields(self) -> None:
        result = ProvisionResult(success=True, tasks=(("packages", "ok"),))
        assert result.success is True
        assert result.tasks == (("packages", "ok"),)

    def test_frozen(self) -> None:
        result = ProvisionResult(success=True, tasks=())
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_hashable(self) -> None:
        result = ProvisionResult(success=True, tasks=())
        assert isinstance(hash(result), int)

    def test_equality(self) -> None:
        assert ProvisionResult(success=True, tasks=(("packages", "ok"),)) == ProvisionResult(
            success=True, tasks=(("packages", "ok"),)
        )
        assert ProvisionResult(success=True, tasks=()) != ProvisionResult(success=False, tasks=())
