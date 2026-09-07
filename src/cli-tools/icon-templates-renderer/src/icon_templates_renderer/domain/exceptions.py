from __future__ import annotations

from pathlib import Path


class IconRendererError(Exception):
    """Base exception for all icon renderer errors."""


class InvalidYamlError(IconRendererError):
    """YAML file is missing, malformed, or fails schema validation."""


class IconNotFoundError(IconRendererError):
    """The requested icon key is not present in the YAML file."""

    def __init__(self, name: str, yaml_path: Path | None = None) -> None:
        self.name = name
        self.yaml_path = yaml_path
        location = yaml_path if yaml_path is not None else "(config)"
        super().__init__(f"Icon '{name}' not found in {location}")


class TemplateNotFoundError(IconRendererError):
    """An SVG template file does not exist at the resolved path."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Template not found: {path}")


class VariantNotFoundError(IconRendererError):
    """The requested variant is not present in the icon group."""

    def __init__(self, name: str, group: str | None = None) -> None:
        self.name = name
        self.group = group
        location = f"in icon '{group}'" if group is not None else "(config)"
        super().__init__(f"Variant '{name}' not found {location}")


class UnknownTokenError(IconRendererError):
    """A mapping token is neither a #rrggbb literal nor a color scheme key."""

    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__(
            f"Token '{token}' is neither a #rrggbb literal nor a key of the color scheme"
        )


class UnknownPlaceholderError(IconRendererError):
    """A placeholder name is not defined in the vocabulary file."""

    def __init__(self, name: str, yaml_path: Path | None = None) -> None:
        self.name = name
        self.yaml_path = yaml_path
        location = yaml_path if yaml_path is not None else "(vocabulary)"
        super().__init__(f"Placeholder '{name}' is not defined in the vocabulary: {location}")


class ColorSchemeNotFoundError(IconRendererError):
    """The color scheme file does not exist or its format is unsupported."""


class MissingMappingError(IconRendererError):
    """A {{placeholder}} in an SVG has no entry in the color_mappings for this icon."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Placeholder '{{{{{key}}}}}' has no entry in color_mappings")


class ColorSchemeKeyNotFoundError(IconRendererError):
    """A color_mappings value references a color scheme key that does not exist."""

    def __init__(self, key: str, scheme_key: str) -> None:
        self.key = key
        self.scheme_key = scheme_key
        super().__init__(
            f"color_mappings entry for '{key}' references color scheme key"
            f" '{scheme_key}' which does not exist"
        )


class ConfigResolutionError(IconRendererError):
    """A required root could not be resolved by the orchestrator.

    ``name`` is the human-friendly lever name (e.g. ``templates_dir``); ``levers``
    is the ordered list of ways the user may provide it, formatted into the
    final message as the actionable hint.
    """

    def __init__(self, name: str, levers: tuple[str, ...]) -> None:
        self.name = name
        self.levers = levers
        hint = " or ".join(levers) if levers else "(no levers available)"
        super().__init__(f"Could not resolve required root '{name}'. Set it via {hint}.")


__all__ = [
    "ColorSchemeKeyNotFoundError",
    "ColorSchemeNotFoundError",
    "ConfigResolutionError",
    "IconNotFoundError",
    "IconRendererError",
    "InvalidYamlError",
    "MissingMappingError",
    "TemplateNotFoundError",
    "UnknownPlaceholderError",
    "UnknownTokenError",
    "VariantNotFoundError",
]
