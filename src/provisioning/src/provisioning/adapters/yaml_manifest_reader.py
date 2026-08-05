"""YAML manifest adapter.

Reads one ``dotfiles/provisioning/*.yaml`` manifest into a domain
``ProvisionManifest``. The use case (Story 1.6) globs the manifest directory;
this adapter never globs.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from provisioning.domain.models import ProvisionManifest, Spec
from provisioning.ports import IManifestReader


class ManifestReadError(ValueError):
    """Raised when a manifest is unreadable, malformed, or incomplete."""


_ALLOWED_MANIFEST_KEYS = frozenset({"kind", "entries"})
_ALLOWED_SPEC_KEYS = frozenset({"name", "version"})


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


def _read_kind(data: dict[str, object], path: Path) -> str:
    kind = data.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        raise ManifestReadError(f"manifest {path} is missing a non-empty 'kind'")
    return kind.strip()


def _read_entries(data: dict[str, object], path: Path) -> tuple[Spec, ...]:
    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list):
        raise ManifestReadError(
            f"manifest {path} 'entries' must be a list, got {type(raw_entries).__name__}"
        )
    return tuple(_parse_spec(index, raw, path) for index, raw in enumerate(raw_entries))


def _parse_spec(index: int, raw: object, path: Path) -> Spec:
    if not isinstance(raw, dict):
        raise ManifestReadError(
            f"manifest {path} entry {index} must be a mapping, got {type(raw).__name__}"
        )
    unknown = set(raw) - _ALLOWED_SPEC_KEYS
    if unknown:
        raise ManifestReadError(
            f"manifest {path} entry {index} has unknown keys: {', '.join(sorted(unknown))}"
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
    return Spec(name=name.strip(), version=version if version else None)


class YamlManifestReader(IManifestReader):
    """Parse one declarative YAML manifest into a ``ProvisionManifest``."""

    def read(self, manifest_path: Path) -> ProvisionManifest:
        data = _read_payload(manifest_path)
        return ProvisionManifest(
            kind=_read_kind(data, manifest_path),
            entries=_read_entries(data, manifest_path),
        )


__all__ = ["ManifestReadError", "YamlManifestReader"]
