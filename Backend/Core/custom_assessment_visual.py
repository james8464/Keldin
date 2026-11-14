"""Render one private source page for local visual assessment analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from hashlib import sha256

import pymupdf

from Backend.Core.custom_assessment_evidence import (
    MAX_PAGES_PER_SOURCE,
    MAX_SOURCE_BYTES,
    LocalSource,
    SourceRole,
)

MAX_IMAGE_EDGE = 2048
MAX_IMAGE_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class VisualPageEvidence:
    role: SourceRole
    document_sha256: str
    page: int
    width_points: float
    height_points: float
    width_pixels: int
    height_pixels: int
    png: bytes


def render_custom_source_page(source: LocalSource, page: int) -> VisualPageEvidence:
    """Rasterize just one page, including scans, without writing or sending it."""
    content = source.content
    if len(content) > MAX_SOURCE_BYTES:
        raise ValueError("Source exceeds the file size limit")
    if not content.startswith(b"%PDF-"):
        raise ValueError("Source must be a readable PDF")
    if type(page) is not int or not 1 <= page <= MAX_PAGES_PER_SOURCE:
        raise ValueError("Invalid source page number")
    try:
        with pymupdf.open(stream=content, filetype="pdf") as document:
            if document.needs_pass or document.is_repaired:
                raise ValueError("Source must be an unlocked, readable PDF")
            if not page <= document.page_count <= MAX_PAGES_PER_SOURCE:
                raise ValueError("Invalid source page count or page number")
            original = document[page - 1]
            width, height = original.rect.width, original.rect.height
            if not all(math.isfinite(edge) and edge > 0 for edge in (width, height)):
                raise ValueError("Invalid source page dimensions")
            # Leave rounding room at the bounding box and never exceed 144 dpi.
            scale = min(2.0, (MAX_IMAGE_EDGE - 2) / max(width, height))
            image = original.get_pixmap(
                matrix=pymupdf.Matrix(scale, scale),
                colorspace=pymupdf.csRGB,
                alpha=False,
                annots=False,
            )
            if not all(
                1 <= edge <= MAX_IMAGE_EDGE for edge in (image.width, image.height)
            ):
                raise ValueError("Source image dimensions exceed the visual limit")
            png = image.tobytes("png")
            if len(png) > MAX_IMAGE_BYTES:
                raise ValueError("Source image exceeds the visual size limit")
            return VisualPageEvidence(
                source.role,
                sha256(content).hexdigest(),
                page,
                width,
                height,
                image.width,
                image.height,
                png,
            )
    except (pymupdf.FileDataError, RuntimeError) as error:
        raise ValueError("Could not render the source page") from error
