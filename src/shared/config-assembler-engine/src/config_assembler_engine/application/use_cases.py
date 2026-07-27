from pathlib import Path

from pydantic import BaseModel

from config_assembler_engine.domain.models import (
    AppliedOverride,
    AssemblyResult,
    DirAssemblyResult,
    OverrideRule,
    OverrideSource,
    ResolutionPolicy,
)
from config_assembler_engine.domain.services import ConfigMergeService, OverrideMatchingService
from config_assembler_engine.errors import (
    ConfigValidationError,
    NotADirectoryError_,
    OverrideCoercionError,
    PathResolutionError,
)
from config_assembler_engine.ports.config_parser import ConfigParserPort
from config_assembler_engine.ports.config_validator import ConfigValidatorPort
from config_assembler_engine.ports.env_reader import EnvironmentReaderPort
from config_assembler_engine.ports.path_resolver import PathResolverPort
from config_assembler_engine.ports.type_coercer import TypeCoercerPort


class AssembleConfiguration:
    def __init__(
        self,
        path_resolver: PathResolverPort,
        parser: ConfigParserPort,
        env_reader: EnvironmentReaderPort,
        validator: ConfigValidatorPort,
        coercer: TypeCoercerPort,
    ) -> None:
        self._path_resolver = path_resolver
        self._parser = parser
        self._env_reader = env_reader
        self._validator = validator
        self._coercer = coercer

    def execute(
        self,
        policy: ResolutionPolicy,
        rules: list[OverrideRule],
        schema: type[BaseModel],
        *,
        cli_overrides: dict[str, str] | None = None,
        explicit_path: str | None = None,
    ) -> AssemblyResult:
        resolved = self._path_resolver.resolve(policy, explicit_path)

        raw = self._parser.parse(resolved.path)

        baseline = self._validator.validate(raw, schema)

        env_vars = self._env_reader.read(policy.env_prefix)

        overrides = OverrideMatchingService.match(env_vars, cli_overrides or {}, rules)

        merged_dict = baseline.model_dump()
        applied: list[AppliedOverride] = []

        sorted_overrides = sorted(
            overrides, key=lambda o: 0 if o.source == OverrideSource.ENV else 1
        )

        for ov in sorted_overrides:
            field_type = self._validator.get_field_info(schema, ov.field_path)
            try:
                coerced = self._coercer.coerce(ov, field_type)
            except OverrideCoercionError:
                raise
            except Exception as e:
                raise OverrideCoercionError(
                    field_path=ov.field_path,
                    raw_value=ov.raw_value,
                    target_type=str(field_type),
                    reason=str(e),
                ) from e

            merged_dict = ConfigMergeService.apply(merged_dict, ov, coerced)
            applied.append(
                AppliedOverride(
                    field_path=ov.field_path,
                    raw_value=ov.raw_value,
                    coerced_value=coerced,
                    source=ov.source,
                )
            )

        try:
            final = self._validator.validate(merged_dict, schema)
        except ConfigValidationError as e:
            e.applied_overrides = applied
            raise

        return AssemblyResult(
            config=final,
            resolved_path=resolved,
            applied_overrides=applied,
        )


class AssembleDir:
    def __init__(
        self,
        path_resolver: PathResolverPort,
        file_pattern: str = "*",
    ) -> None:
        self._path_resolver = path_resolver
        self._file_pattern = file_pattern

    def execute(
        self,
        policy: ResolutionPolicy,
        *,
        explicit_path: str | None = None,
    ) -> DirAssemblyResult:
        resolved = self._path_resolver.resolve(policy, explicit_path)
        if not resolved.path.is_dir():
            raise NotADirectoryError_(f"Resolved path is not a directory: {resolved.path}")
        files = sorted(resolved.path.glob(self._file_pattern))
        return DirAssemblyResult(
            directory=resolved.path,
            source=resolved.source,
            files=files,
        )
