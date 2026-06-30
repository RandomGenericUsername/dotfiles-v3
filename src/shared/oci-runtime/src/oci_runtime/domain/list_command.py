def build_list_command(
    binary: str,
    subcommand: list[str],
    format_flags: tuple[str, ...],
    show_all: bool = False,
    filters: dict[str, str] | None = None,
) -> list[str]:
    cmd = [binary] + subcommand
    cmd.extend(format_flags)
    if show_all:
        cmd.append("-a")
    if filters:
        for key, val in filters.items():
            cmd.extend(["--filter", f"{key}={val}"])
    return cmd
