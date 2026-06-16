from dataclasses import dataclass, field


@dataclass(frozen=True)
class RuntimeCapabilities:
    list_format_flags: list[str] = field(default_factory=list)
    needs_userns_keep_id: bool = False
    supports_log_drivers: bool = True
    tar_entry_name: str = "Dockerfile"
    default_run_flags: list[str] = field(default_factory=list)
    default_build_flags: list[str] = field(default_factory=list)
