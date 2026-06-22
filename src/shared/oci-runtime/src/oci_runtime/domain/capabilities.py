from dataclasses import dataclass, field


@dataclass(frozen=True)
class RuntimeCapabilities:
    list_format_flags: tuple[str, ...] = field(default_factory=tuple)
    needs_userns_keep_id: bool = False
    supports_log_drivers: bool = False
    tar_entry_name: str = ""
    default_run_flags: tuple[str, ...] = field(default_factory=tuple)
    default_build_flags: tuple[str, ...] = field(default_factory=tuple)
