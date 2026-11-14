from hashlib import sha256

import pymupdf
import pytest

from Backend.Core.custom_assessment_evidence import LocalSource
from Backend.Core.custom_assessment_visual import (
    MAX_IMAGE_EDGE,
    render_custom_source_page,
)


def test_scan_preserves_visible_content_without_embedded_text() -> None:
    with pymupdf.open() as artwork:
        page = artwork.new_page(width=450, height=300)
        page.draw_rect(pymupdf.Rect(40, 50, 400, 80), fill=(0, 0, 0))
        pixels = page.get_pixmap()
        with pymupdf.open() as scan:
            scan.new_page(width=450, height=300).insert_image(page.rect, pixmap=pixels)
            assert not scan[0].get_text().strip()
            data = scan.tobytes()
    evidence = render_custom_source_page(LocalSource("question-paper", data), 1)
    assert evidence.document_sha256 == sha256(data).hexdigest()
    assert (evidence.page, evidence.width_points, evidence.height_points) == (
        1,
        450,
        300,
    )
    image = pymupdf.Pixmap(evidence.png)
    assert image.pixel(100, 120) == (0, 0, 0)
    assert image.pixel(10, 10) == (255, 255, 255)


def test_large_page_is_bounded_and_keeps_its_aspect_ratio() -> None:
    with pymupdf.open() as document:
        document.new_page(width=3000, height=6000)
        data = document.tobytes()
    evidence = render_custom_source_page(LocalSource("syllabus", data), 1)
    assert max(evidence.width_pixels, evidence.height_pixels) <= MAX_IMAGE_EDGE
    assert evidence.width_pixels / evidence.height_pixels == pytest.approx(
        0.5, abs=0.001
    )


@pytest.mark.parametrize("page", [True, 0, 2])
def test_invalid_page_is_not_silently_substituted(page: int) -> None:
    with pymupdf.open() as document:
        document.new_page()
        data = document.tobytes()
    with pytest.raises(ValueError, match="Invalid source page"):
        render_custom_source_page(LocalSource("question-paper", data), page)
