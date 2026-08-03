from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from icon_templates_renderer.adapters.schemas.icons_config_schema import (
    IconGroupSchema,
    VariantSchema,
)
from icon_templates_renderer.domain.exceptions import IconNotFoundError, InvalidYamlError
from icon_templates_renderer.domain.models import (
    IconConfig,
    IconGroup,
    ResolvedRoots,
    Variant,
)
from icon_templates_renderer.domain.services import PathResolutionService

_REQUIRED_GROUP_FIELDS = ("variants",)
_REQUIRED_VARIANT_FIELDS = ("name", "template", "output")


class YamlIconConfigLoader:
    def __init__(self, path_resolution_service: PathResolutionService | None = None) -> None:
        self._path_service = path_resolution_service or PathResolutionService()
        self._resolved_path: Path | None = None

    def load(self, yaml_path: Path, roots: ResolvedRoots | None = None) -> IconConfig:
        if not yaml_path.exists():
            raise InvalidYamlError(f"YAML file not found: {yaml_path}")

        with yaml_path.open() as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise InvalidYamlError(f"Failed to parse YAML: {e}") from e

        if not isinstance(data, dict):
            raise InvalidYamlError("YAML root must be a mapping of icon group keys")

        roots = roots or ResolvedRoots()
        self._resolved_path = yaml_path

        groups = tuple(self._parse_group(name, config, roots) for name, config in data.items())
        return IconConfig(groups=groups)

    def load_one(self, yaml_path: Path, icon: str, roots: ResolvedRoots | None = None) -> IconGroup:
        config = self.load(yaml_path, roots)
        for group in config.groups:
            if group.name == icon:
                return group
        raise IconNotFoundError(icon, yaml_path)

    def get_resolved_path(self) -> Path | None:
        return self._resolved_path

    def _parse_group(
        self,
        name: str,
        config: dict[str, Any],
        roots: ResolvedRoots,
    ) -> IconGroup:
        for field in _REQUIRED_GROUP_FIELDS:
            if field not in config:
                raise InvalidYamlError(f"Icon '{name}' is missing required field: '{field}'")

        for variant_config in config.get("variants") or []:
            for field in _REQUIRED_VARIANT_FIELDS:
                if field not in variant_config:
                    raise InvalidYamlError(
                        f"A variant in icon '{name}' is missing required field: '{field}'"
                    )

        group_schema = IconGroupSchema(**config)

        template_dir = self._path_service.resolve(roots.template_root, group_schema.template_dir)
        output_dir = self._path_service.resolve(roots.output_root, group_schema.output_dir)

        variants = tuple(
            self._parse_variant(name, v, template_dir, output_dir) for v in group_schema.variants
        )

        return IconGroup(
            name=name,
            template_dir=template_dir,
            output_dir=output_dir,
            unsafe=group_schema.unsafe,
            color_mappings=dict(group_schema.color_mappings),
            variants=variants,
        )

    def _parse_variant(
        self,
        group_name: str,
        variant_schema: VariantSchema,
        template_dir: Path | None,
        output_dir: Path | None,
    ) -> Variant:
        template = self._path_service.resolve(template_dir, variant_schema.template)
        output = self._path_service.resolve(output_dir, variant_schema.output)
        return Variant(
            name=variant_schema.name,
            template=template if template is not None else Path(variant_schema.template),
            output=output if output is not None else Path(variant_schema.output),
            color_mappings=dict(variant_schema.color_mappings),
        )
