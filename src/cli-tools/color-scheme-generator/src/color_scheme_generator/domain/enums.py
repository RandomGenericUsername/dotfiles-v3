from __future__ import annotations

from enum import Enum


class Backend(Enum):
    CUSTOM = "custom"
    PYWAL = "pywal"
    WALLUST = "wallust"

    @property
    def install_hint(self) -> str:
        hints = {
            Backend.CUSTOM: "pip install color-scheme-generator[custom]",
            Backend.PYWAL: "pip install color-scheme-generator[pywal]",
            Backend.WALLUST: "Install wallust binary",
        }
        return hints[self]

    @property
    def image_suffix(self) -> str:
        return self.value


class ColorAlgorithm(Enum):
    WAL = "wal"
    COLORZ = "colorz"
    HAISHOKU = "haishoku"


class ColorFormat(Enum):
    JSON = "json"
    SH = "sh"
    CSS = "css"
    GTK_CSS = "gtk.css"
    ADW_CSS = "adw.css"
    YAML = "yaml"
    SEQUENCES = "sequences"
    RASI = "rasi"
    SCSS = "scss"
    HYPRLAND = "conf"
    KITTY = "kitty"
    # btop theme formats. Multi-dot values are fine: the catalog strips the
    # "colors." prefix and passes the remainder to ColorFormat() (GTK_CSS is
    # the existing precedent). These three form a difficulty dial -- minimal
    # is all ramp slices, balanced additionally forces temp_* and cached_*
    # semantic, full additionally forces cpu_*. A member and its
    # colors.<value>.j2 template are one inseparable unit: an unregistered
    # template raises TemplatesValidationError and breaks csg entirely.
    BTOP_MINIMAL = "btop-minimal.theme"
    BTOP_BALANCED = "btop-balanced.theme"
    BTOP_FULL = "btop-full.theme"


class RuntimeMode(Enum):
    LOCAL = "local"
    CONTAINER = "container"


class ContainerEngine(Enum):
    DOCKER = "docker"
    PODMAN = "podman"


class OutputFormat(Enum):
    JSON = "json"
    RICH = "rich"
    PLAIN = "plain"

    def __str__(self) -> str:
        return self.value


class Verbosity(Enum):
    QUIET = 0
    NORMAL = 1
    VERBOSE = 2
    DEBUG = 3
