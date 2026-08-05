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


class BinaryCapability(StrEnum):
    """Binaries and CLI tools provisioning must place on PATH."""

    HYPRLAND = "Hyprland"
    HYPRPAPER = "Hyprpaper"
    WAYBAR = "Waybar"
    FONTS = "fonts"
    CSG = "csg"
    WEG = "weg"
    ICON_RENDERER = "icon-renderer"


class AssetKind(StrEnum):
    """Kinds of assets deployed into the install spine."""

    WALLPAPER = "wallpaper"
    ICON_TEMPLATE = "icon-template"
    ICON_MAPPING = "icon-mapping"
    CSG_TEMPLATE = "csg-template"
    WEG_EFFECTS = "weg-effects"
