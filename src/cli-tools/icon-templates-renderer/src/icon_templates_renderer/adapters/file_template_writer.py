from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from icon_templates_renderer.domain.exceptions import (
    TemplateNotFoundError,
    TemplatePaintAttributeError,
    UnknownTemplateShapeError,
)
from icon_templates_renderer.domain.models import (
    TemplateAnalysis,
    TemplateSetPlaceholderRequest,
)
from icon_templates_renderer.domain.services import (
    TemplateAnalysisService,
    attr_value,
    validate_placeholder_name,
)


class FileTemplateWriter:
    """Raw string-surgery template writes: analyze + single-shape placeholder assignment.

    Mirrors the GUI extractor for shape numbering and root paint inheritance.
    Writes are byte-preserving outside the edited attribute and atomic (temp
    file + rename) so an interrupted write never truncates a template.
    """

    def __init__(self, service: TemplateAnalysisService | None = None) -> None:
        self._service = service or TemplateAnalysisService()

    def analyze(self, path: Path) -> TemplateAnalysis:
        body = self._read(path)
        shapes = self._service.analyze(body)
        return TemplateAnalysis(path=path, mode=self._service.classify(shapes), shapes=shapes)

    def set_placeholder(self, request: TemplateSetPlaceholderRequest) -> TemplateAnalysis:
        validate_placeholder_name(request.name)
        body = self._read(request.path)
        pairs = self._service.extract_with_elements(body)
        target = next(
            ((shape, element) for shape, element in pairs if shape.shape_id == request.shape_id),
            None,
        )
        if target is None:
            raise UnknownTemplateShapeError(request.shape_id, request.path)
        shape, element = target
        if attr_value(element, shape.paint_attr) is None:
            raise TemplatePaintAttributeError(request.shape_id, shape.paint_attr, request.path)
        new_element = self._set_attr_value(element, shape.paint_attr, f"{{{{{request.name}}}}}")
        new_text = body.replace(element, new_element, 1)
        self._atomic_write(request.path, new_text)
        return self.analyze(request.path)

    @staticmethod
    def _set_attr_value(element: str, attr: str, value: str) -> str:
        pattern = re.compile(rf'(\b{re.escape(attr)}\s*=\s*")([^"]*)(")')

        def repl(match: re.Match[str]) -> str:
            return match.group(1) + value + match.group(3)

        return pattern.sub(repl, element, count=1)

    @staticmethod
    def _read(path: Path) -> str:
        try:
            # newline="" preserves CRLF/LF exactly so a rewrite is byte-identical
            # outside the edited attribute (universal-newline translation would
            # silently normalize line endings).
            with path.open("r", encoding="utf-8", newline="") as handle:
                return handle.read()
        except OSError:
            raise TemplateNotFoundError(path) from None

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        tmp: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=path.parent,
                delete=False,
                mode="w",
                encoding="utf-8",
                newline="",
            ) as handle:
                tmp = handle.name
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        except BaseException:
            if tmp is not None:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
            raise
