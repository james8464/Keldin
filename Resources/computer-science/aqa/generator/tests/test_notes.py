from pathlib import Path

import pytest
from cspapergen.notes import cache_notes, discover_note_pdfs
from reportlab.pdfgen.canvas import Canvas

NUMBER_SYSTEMS = "5.1. Number Systems.pdf"
FUNCTIONAL_PROGRAMS = "12.2. Writing Functional Programs.pdf"


def _write_note(path: Path, content: str) -> None:
    canvas = Canvas(str(path))
    canvas.drawString(54, 740, content)
    canvas.save()


@pytest.fixture
def notes_fixture(tmp_path):
    source = tmp_path / "notes with spaces"
    source.mkdir()
    originals = {
        NUMBER_SYSTEMS: "Binary uses two digit values.",
        FUNCTIONAL_PROGRAMS: "A pure function does not modify external state.",
    }
    for name, content in originals.items():
        _write_note(source / name, content)
    (source / "readme.txt").write_text("Original test notes only.", encoding="utf-8")
    (source / "nested").mkdir()
    _write_note(source / "nested/unrelated.pdf", "Not a top-level note.")
    return source, originals


def test_discovers_top_level_pdfs_in_stable_order(notes_fixture):
    source, _ = notes_fixture
    assert discover_note_pdfs(source) == [
        source / FUNCTIONAL_PROGRAMS,
        source / NUMBER_SYSTEMS,
    ]
    assert discover_note_pdfs(source / "missing") == []


def test_cache_notes_extracts_each_pdf_into_the_requested_cache(
    notes_fixture, tmp_path
):
    source, originals = notes_fixture
    cache = tmp_path / "isolated cache"

    manifest = cache_notes(source, cache)

    assert manifest.source_dir == source
    assert manifest.cache_dir == cache
    assert manifest.pdf_count == manifest.text_count == len(originals)
    assert sorted(path.name for path in (cache / "raw").iterdir()) == sorted(originals)
    assert sorted(path.stem for path in (cache / "text").iterdir()) == sorted(
        Path(name).stem for name in originals
    )
    for name, content in originals.items():
        assert (cache / "raw" / name).read_bytes() == (source / name).read_bytes()
        text = (cache / "text" / f"{Path(name).stem}.txt").read_text(encoding="utf-8")
        assert text.strip() == content
