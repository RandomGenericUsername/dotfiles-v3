from __future__ import annotations

from provisioning.domain.enums import AssetKind, BinaryCapability, Distro
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


class TestBinaryCapability:
    def test_members(self) -> None:
        assert BinaryCapability.HYPRLAND.value == "Hyprland"
        assert BinaryCapability.HYPRPAPER.value == "Hyprpaper"
        assert BinaryCapability.WAYBAR.value == "Waybar"
        assert BinaryCapability.CSG.value == "csg"
        assert BinaryCapability.WEG.value == "weg"
        assert BinaryCapability.ICON_RENDERER.value == "icon-renderer"

    def test_fonts_covered(self) -> None:
        assert BinaryCapability.FONTS.value == "fonts"


class TestAssetKind:
    def test_members(self) -> None:
        assert AssetKind.WALLPAPER.value == "wallpaper"
        assert AssetKind.ICON_TEMPLATE.value == "icon-template"
        assert AssetKind.ICON_MAPPING.value == "icon-mapping"
        assert AssetKind.CSG_TEMPLATE.value == "csg-template"
        assert AssetKind.WEG_EFFECTS.value == "weg-effects"


class TestSpec:
    def test_constructs_with_all_fields(self) -> None:
        spec = Spec(name="hyprland", version="0.1.0")
        assert spec.name == "hyprland"
        assert spec.version == "0.1.0"

    def test_frozen(self) -> None:
        spec = Spec(name="hyprland", version="0.1.0")
        try:
            spec.name = "waybar"  # type: ignore[misc]
        except AttributeError:
            pass
        else:
            raise AssertionError("Spec must be frozen")

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
        try:
            state.install_dir = "/y"  # type: ignore[misc]
        except AttributeError:
            pass
        else:
            raise AssertionError("MachineState must be frozen")

    def test_equality(self) -> None:
        assert MachineState(distro=Distro.ARCH, install_dir="/x") == MachineState(
            distro=Distro.ARCH, install_dir="/x"
        )
        assert MachineState(distro=Distro.ARCH, install_dir="/x") != MachineState(
            distro=Distro.DEBIAN_FAMILY, install_dir="/x"
        )


class TestProvisionManifest:
    def test_constructs_with_all_fields(self) -> None:
        manifest = ProvisionManifest(kind="packages", entries=[Spec(name="hyprland", version=None)])
        assert manifest.kind == "packages"
        assert len(manifest.entries) == 1

    def test_frozen(self) -> None:
        manifest = ProvisionManifest(kind="packages", entries=[])
        try:
            manifest.kind = "assets"  # type: ignore[misc]
        except AttributeError:
            pass
        else:
            raise AssertionError("ProvisionManifest must be frozen")

    def test_equality(self) -> None:
        entries = [Spec(name="hyprland", version=None)]
        assert ProvisionManifest(kind="packages", entries=entries) == ProvisionManifest(
            kind="packages", entries=entries
        )
        assert ProvisionManifest(kind="packages", entries=entries) != ProvisionManifest(
            kind="assets", entries=entries
        )


class TestProvisionResult:
    def test_constructs_with_all_fields(self) -> None:
        result = ProvisionResult(success=True, tasks=[("packages", "ok")])
        assert result.success is True
        assert result.tasks == [("packages", "ok")]

    def test_frozen(self) -> None:
        result = ProvisionResult(success=True, tasks=[])
        try:
            result.success = False  # type: ignore[misc]
        except AttributeError:
            pass
        else:
            raise AssertionError("ProvisionResult must be frozen")

    def test_equality(self) -> None:
        assert ProvisionResult(success=True, tasks=[("packages", "ok")]) == ProvisionResult(
            success=True, tasks=[("packages", "ok")]
        )
        assert ProvisionResult(success=True, tasks=[]) != ProvisionResult(success=False, tasks=[])
