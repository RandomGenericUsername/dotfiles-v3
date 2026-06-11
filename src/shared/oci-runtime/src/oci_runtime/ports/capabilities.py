from dataclasses import dataclass, field

from oci_runtime.domain.enums import RuntimeKind


@dataclass(frozen=True)
class EngineProfile:
    binary: str
    kind: RuntimeKind


@dataclass(frozen=True)
class RuntimePreference:
    """Explicit user declaration of what engine to use.

    No guessing, no fallback. The binary must be explicitly declared.
    If the requested engine is not available, creation fails immediately.
    """
    kind: RuntimeKind
    binary: str


@dataclass
class RuntimeCapabilities:
    # Array-based format support for extensibility (replaces supports_json_output)
    supported_output_formats: list[str] = field(default_factory=lambda: ["json"])
    needs_userns_keep_id: bool = False
    supports_log_drivers: bool = True
    tar_entry_name: str = "Dockerfile"
    default_run_flags: list[str] = field(default_factory=list)
    default_build_flags: list[str] = field(default_factory=list)
