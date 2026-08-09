"""YAML manifest adapter.

Reads one ``dotfiles/provisioning/*.yaml`` manifest into a domain
``ProvisionManifest``. The use case (Story 1.6) globs the manifest directory;
this adapter never globs.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from provisioning.domain.enums import AssetKind, ManifestKind
from provisioning.domain.models import ProvisionManifest, Spec
from provisioning.ports import IManifestReader


class ManifestReadError(ValueError):
    """Raised when a manifest is unreadable, malformed, or incomplete."""


_ALLOWED_MANIFEST_KEYS = frozenset({"kind", "entries"})

_EntrySchema = tuple[frozenset[str], frozenset[str]]

# Per-kind entry schema: (allowed keys, required keys). Rich per-kind keys
# (``target``, ``source``, ``kind``) are validated here but NOT captured into
# the returned ``Spec`` — Ansible is the consumer of the full YAML.
_ENTRY_SCHEMAS: dict[ManifestKind, _EntrySchema] = {
    ManifestKind.PACKAGES: (frozenset({"name", "version"}), frozenset({"name"})),
    ManifestKind.ASSETS: (
        frozenset({"name", "version", "kind", "source"}),
        frozenset({"name", "kind"}),
    ),
    ManifestKind.FILESYSTEM: (frozenset({"name"}), frozenset({"name"})),
    ManifestKind.SYMLINKS: (
        frozenset({"name", "target", "version"}),
        frozenset({"name", "target"}),
    ),
    ManifestKind.CLI_TOOLS: (
        frozenset({"name", "source", "version"}),
        frozenset({"name", "source"}),
    ),
}


class _StrictSafeLoader(yaml.SafeLoader):  # type: ignore[misc]
    """SafeLoader that rejects duplicate mapping keys."""


def _construct_mapping(
    loader: _StrictSafeLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[str, object]:
    mapping: dict[str, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found a non-string key",
                key_node.start_mark,
            )
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def _read_payload(path: Path) -> dict[str, object]:
    try:
        with path.open(encoding="utf-8") as stream:
            data = yaml.load(stream, Loader=_StrictSafeLoader)
    except OSError as exc:
        raise ManifestReadError(f"cannot read manifest {path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ManifestReadError(f"manifest {path} is not valid UTF-8: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ManifestReadError(f"invalid YAML in manifest {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestReadError(f"manifest {path} must be a mapping, got {type(data).__name__}")
    unknown = set(data) - _ALLOWED_MANIFEST_KEYS
    if unknown:
        raise ManifestReadError(f"manifest {path} has unknown keys: {', '.join(sorted(unknown))}")
    return data


def _read_kind(data: dict[str, object], path: Path) -> ManifestKind:
    raw_kind = data.get("kind")
    if not isinstance(raw_kind, str) or not raw_kind.strip():
        raise ManifestReadError(f"manifest {path} is missing a non-empty 'kind'")
    kind_value = raw_kind.strip()
    try:
        return ManifestKind(kind_value)
    except ValueError as exc:
        supported = ", ".join(sorted(member.value for member in ManifestKind))
        raise ManifestReadError(
            f"manifest {path} has unknown kind {kind_value!r}; supported kinds: {supported}"
        ) from exc


def _read_entries(data: dict[str, object], path: Path, kind: ManifestKind) -> tuple[Spec, ...]:
    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list):
        raise ManifestReadError(
            f"manifest {path} 'entries' must be a list, got {type(raw_entries).__name__}"
        )
    return tuple(_parse_spec(index, raw, path, kind) for index, raw in enumerate(raw_entries))


def _parse_spec(index: int, raw: object, path: Path, kind: ManifestKind) -> Spec:
    allowed_keys, required_keys = _ENTRY_SCHEMAS[kind]
    if not isinstance(raw, dict):
        raise ManifestReadError(
            f"manifest {path} entry {index} must be a mapping, got {type(raw).__name__}"
        )
    unknown = set(raw) - allowed_keys
    if unknown:
        raise ManifestReadError(
            f"manifest {path} entry {index} has unknown keys: {', '.join(sorted(unknown))}"
        )
    missing = required_keys - set(raw)
    if missing:
        raise ManifestReadError(
            f"manifest {path} entry {index} is missing required keys: {', '.join(sorted(missing))}"
        )
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ManifestReadError(f"manifest {path} entry {index} is missing a non-empty 'name'")
    version = raw.get("version")
    if version is not None and not isinstance(version, str):
        raise ManifestReadError(
            f"manifest {path} entry {index} 'version' must be a string or null, "
            f"got {type(version).__name__}"
        )
    _validate_rich_kind(index, raw, path, kind)
    return Spec(name=name.strip(), version=version if version else None)


def _validate_rich_kind(index: int, raw: dict[str, object], path: Path, kind: ManifestKind) -> None:
    """Validate rich per-kind keys (assets ``kind``, ``source``) without capturing them."""
    if kind is ManifestKind.ASSETS:
        asset_kind = raw.get("kind")
        if not isinstance(asset_kind, str) or not asset_kind.strip():
            raise ManifestReadError(
                f"manifest {path} entry {index} is missing a non-empty asset 'kind'"
            )
        try:
            AssetKind(asset_kind.strip())
        except ValueError as exc:
            supported = ", ".join(sorted(member.value for member in AssetKind))
            raise ManifestReadError(
                f"manifest {path} entry {index} has unknown AssetKind "
                f"{asset_kind.strip()!r}; supported: {supported}"
            ) from exc


class YamlManifestReader(IManifestReader):
    """Parse one declarative YAML manifest into a ``ProvisionManifest``."""

    def read(self, manifest_path: Path) -> ProvisionManifest:
        data = _read_payload(manifest_path)
        kind = _read_kind(data, manifest_path)
        return ProvisionManifest(
            kind=kind,
            entries=_read_entries(data, manifest_path, kind),
        )


__all__ = ["ManifestReadError", "YamlManifestReader"]
