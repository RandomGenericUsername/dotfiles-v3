from __future__ import annotations

from importlib.resources import files as resource_files
from pathlib import Path

from wallpaper_effects_generator.ports.output import OutputPort


def dump_config_command(
    output_adapter: OutputPort,
    output_path: Path | None = None,
    message_adapter: OutputPort | None = None,
) -> None:
    content = (
        resource_files("wallpaper_effects_generator.defaults")
        .joinpath("settings.toml")
        .read_text()
    )
    if output_path:
        if output_path.suffix != ".toml":
            output_path = output_path / "settings.toml"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        (message_adapter or output_adapter).message(f"Default config written to {output_path}")
        return
    output_adapter.dump_config_template(content)
