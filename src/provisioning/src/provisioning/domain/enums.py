"""Pure, zero-I/O enums for the provisioning domain."""

from __future__ import annotations

from enum import StrEnum


class Distro(StrEnum):
    """Supported target distributions.

    Values MUST match the ``group_vars`` filenames so ``IFactReader.os_family()``
    maps directly onto this enum (the ``os_family`` seam contract).
    """

    ARCH = "arch"
    DEBIAN_FAMILY = "debian-family"


class CapabilityKind(StrEnum):
    """How a capability is verified on the target machine.

    ``BINARY`` capabilities are executables that must resolve on PATH.
    ``PACKAGE_GROUP`` capabilities are sets of packages installed through the
    package manager — no PATH lookup applies.
    """

    BINARY = "binary"
    PACKAGE_GROUP = "package-group"


class Capability(StrEnum):
    """Capabilities provisioning must ensure are present on the target.

    Values are the real on-PATH executable names (e.g. ``Hyprland``,
    ``hyprpaper``, ``itr``) or the package-group key (``fonts``). The
    verification method for each member is exposed via :meth:`kind`.
    """

    HYPRLAND = "Hyprland"
    HYPRPAPER = "hyprpaper"
    WAYBAR = "waybar"
    FONTS = "fonts"
    CSG = "csg"
    WEG = "weg"
    ICON_RENDERER = "itr"

    def kind(self) -> CapabilityKind:
        """Return how this capability is verified on the target machine."""
        return _KIND_BY_CAPABILITY[self]


_KIND_BY_CAPABILITY: dict[Capability, CapabilityKind] = {
    Capability.HYPRLAND: CapabilityKind.BINARY,
    Capability.HYPRPAPER: CapabilityKind.BINARY,
    Capability.WAYBAR: CapabilityKind.BINARY,
    Capability.CSG: CapabilityKind.BINARY,
    Capability.WEG: CapabilityKind.BINARY,
    Capability.ICON_RENDERER: CapabilityKind.BINARY,
    Capability.FONTS: CapabilityKind.PACKAGE_GROUP,
}


class ManifestKind(StrEnum):
    """The concrete kinds of declarative manifests under ``dotfiles/provisioning/``.

    Values are the manifest ``kind`` values; the install-spine target for
    ``ASSETS`` entries is resolved via :meth:`AssetKind.spine_segment` (the
    two enums serve different purposes — kind of manifest vs kind of asset).
    """

    PACKAGES = "packages"
    ASSETS = "assets"
    FILESYSTEM = "filesystem"
    SYMLINKS = "symlinks"
    CLI_TOOLS = "cli-tools"


class AssetKind(StrEnum):
    """Kinds of assets deployed into the install spine."""

    WALLPAPER = "wallpaper"
    ICON_TEMPLATE = "icon-template"
    ICON_MAPPING = "icon-mapping"
    CSG_TEMPLATE = "csg-template"
    WEG_EFFECTS = "weg-effects"

    def spine_segment(self) -> str:
        """The install-spine deploy target for this asset kind.

        Single source of truth for the path segment under the install dir
        (resolves the Story 1.2 deferred ``icon-mapping`` vs ``icon-mappings``
        mismatch): ``WEG_EFFECTS`` is emitted as a single file, all others
        deploy into a directory of that name.
        """
        return _SPINE_SEGMENT[self]


_SPINE_SEGMENT: dict[AssetKind, str] = {
    AssetKind.WALLPAPER: "wallpapers",
    AssetKind.ICON_TEMPLATE: "icon-templates",
    AssetKind.ICON_MAPPING: "icon-mappings",
    AssetKind.CSG_TEMPLATE: "csg-templates",
    AssetKind.WEG_EFFECTS: "weg-effects.yaml",
}


__all__ = [
    "AssetKind",
    "Capability",
    "CapabilityKind",
    "Distro",
    "ManifestKind",
]
