from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeCapabilities:
    list_format_flags: tuple[str, ...] = ()
    needs_userns_keep_id: bool = False
    supports_log_drivers: bool = False
    tar_entry_name: str = ""
    default_run_flags: tuple[str, ...] = ()
    default_build_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _TUPLE_FIELDS = ("list_format_flags", "default_run_flags", "default_build_flags")
        for name in _TUPLE_FIELDS:
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
