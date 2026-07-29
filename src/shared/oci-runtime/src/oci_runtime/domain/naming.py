from __future__ import annotations


def engine_qualified_image(
    name: str,
    engine: str,
    tag: str,
    registry: str | None = None,
) -> str:
    if not engine:
        raise ValueError("engine is required for an engine-qualified image name")
    repo = f"{name}-{engine}"
    image = f"{repo}:{tag}"
    if registry:
        return f"{registry.rstrip('/')}/{image}"
    return image
