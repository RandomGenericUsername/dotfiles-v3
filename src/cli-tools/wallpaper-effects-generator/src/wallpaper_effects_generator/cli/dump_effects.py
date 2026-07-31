from __future__ import annotations

from importlib.resources import files as resource_files
from pathlib import Path

from wallpaper_effects_generator.ports.output import OutputPort


def dump_effects_command(
    output_adapter: OutputPort,
    output_path: Path | None = None,
    message_adapter: OutputPort | None = None,
) -> None:
    content = (
        resource_files("wallpaper_effects_generator.defaults").joinpath("effects.yaml").read_text()
    )
    if output_path:
        if output_path.suffix != ".yaml":
            output_path = output_path / "effects.yaml"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        (message_adapter or output_adapter).message(f"Default effects written to {output_path}")
        return
    output_adapter.dump_effects_template(content)
