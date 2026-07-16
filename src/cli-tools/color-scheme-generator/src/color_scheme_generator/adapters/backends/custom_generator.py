from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import (
    BackendNotAvailableError,
    InvalidImageError,
)
from color_scheme_generator.domain.models import Color, ColorScheme, GeneratorConfig
from color_scheme_generator.domain.services import (
    ColorAdjustmentService,
    PaletteNormalizationService,
)


class CustomGenerator:
    def is_available(self) -> bool:
        try:
            import numpy  # noqa: F401
            import PIL.Image  # noqa: F401
            import sklearn.cluster  # noqa: F401
            return True
        except ImportError:
            return False

    def generate(self, image_path: Path, config: GeneratorConfig) -> ColorScheme:
        if not self.is_available():
            raise BackendNotAvailableError(
                Backend.CUSTOM, "pip install color-scheme-generator[custom]"
            )

        try:
            import numpy as np
            import PIL.Image
            import sklearn.cluster

            PIL.Image.MAX_IMAGE_PIXELS = None
            img = PIL.Image.open(image_path)
            img = img.resize((200, 200), PIL.Image.Resampling.LANCZOS)

            img_array = np.array(img.convert("RGB"))
            pixels = img_array.reshape(-1, 3)

            params = config.params or {}
            n_clusters = params.get("n_clusters", 16)
            if not isinstance(n_clusters, int):
                n_clusters = 16
            n_clusters = max(1, min(n_clusters, len(pixels)))
            kmeans = sklearn.cluster.KMeans(
                n_clusters=n_clusters, random_state=0, n_init="auto"
            )
            kmeans.fit(pixels)
            centers = kmeans.cluster_centers_.astype(int)

            colors = [
                Color(
                    f"#{int(c[0]):02x}{int(c[1]):02x}{int(c[2]):02x}",
                    (int(c[0]), int(c[1]), int(c[2])),
                )
                for c in centers
            ]

            colors = list(PaletteNormalizationService.normalize(colors))

            saturation = params.get("saturation", 1.0)
            if not isinstance(saturation, (int, float)) or math.isnan(saturation):
                saturation = 1.0
            else:
                saturation = max(0.0, min(1.0, saturation))
            colors = [
                ColorAdjustmentService.adjust_saturation(c, saturation)
                for c in colors
            ]

            colors = PaletteNormalizationService.sort_by_brightness(colors)

            background = colors[0]
            foreground = colors[-1]
            cursor = max(colors, key=lambda c: max(c.rgb) - min(c.rgb))

            return ColorScheme(
                background=background,
                foreground=foreground,
                cursor=cursor,
                colors=tuple(colors),
                source_image=image_path,
                backend=Backend.CUSTOM,
                generated_at=datetime.now(),
            )

        except (OSError, PIL.UnidentifiedImageError) as exc:
            if isinstance(exc, PIL.UnidentifiedImageError):
                raise InvalidImageError(
                    image_path, "PIL cannot decode this image format"
                ) from None
            raise InvalidImageError(
                image_path, f"Cannot read image file: {exc}"
            ) from None
