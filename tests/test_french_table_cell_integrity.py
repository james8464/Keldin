"""Printed material cells must not exchange digits across visible grid lines."""

from copy import deepcopy

import pytest

from Backend.Core.france import llm_pdf
from Backend.Core.france.llm_pipeline import validate_authored_exercise
from tests.test_french_llm_pdf import exercises, render


def sources(*, rows=2, columns=2, wrapped=False):
    raw = [exercise.model_dump(mode="json") for exercise in exercises(graphs=True)]
    material = raw[0]["materials"][0]
    material["columns"] = [f"Colonne {index}" for index in range(columns)]
    value = (
        "Même texte répété pour permettre un retour automatique à la ligne."
        if wrapped
        else "Texte"
    )
    material["rows"] = [[value for _ in range(columns)] for _ in range(rows)]
    material["rows"][0][:2] = ["1", "23"]
    raw[0]["questions"][0]["prompt"] += (
        "\n```python\nr = 0\nfor x in [1, 2]:\n    r = r + x\n```"
    )
    return [
        validate_authored_exercise(item, str(index))
        for index, item in enumerate(raw, 1)
    ]


def changed(source, *, first_row=None, header=None, extra_row=False):
    raw = deepcopy([exercise.model_dump(mode="json") for exercise in source])
    table = raw[0]["materials"][0]
    if first_row is not None:
        table["rows"][0] = first_row
    if header is not None:
        table["columns"] = header
    if extra_row:
        table["rows"].append(table["rows"][-1])
    return [
        validate_authored_exercise(item, str(index))
        for index, item in enumerate(raw, 1)
    ]


@pytest.mark.parametrize("large_print", [False, True])
@pytest.mark.parametrize("correction", [False, True])
def test_numeric_cell_boundaries_cannot_be_erased(tmp_path, large_print, correction):
    source = sources()
    wrong = changed(source, first_row=["12", "3"])
    path = tmp_path / "wrong.pdf"
    render(path, wrong, correction=correction, large_print=large_print)
    with pytest.raises(ValueError, match=r"[Cc]ell|tableau|colonne"):
        llm_pdf.validate_llm_pdf(
            path, source, correction=correction, large_print=large_print
        )


@pytest.mark.parametrize("large_print", [False, True])
@pytest.mark.parametrize("correction", [False, True])
@pytest.mark.parametrize("shape", [(2, 2, False), (30, 2, True), (3, 8, False)])
def test_valid_material_cells_wrap_repeat_and_keep_source(
    tmp_path, large_print, correction, shape
):
    rows, columns, wrapped = shape
    source = sources(rows=rows, columns=columns, wrapped=wrapped)
    before = [exercise.model_dump_json() for exercise in source]
    path = tmp_path / "valid.pdf"
    render(path, source, correction=correction, large_print=large_print)
    llm_pdf.validate_llm_pdf(
        path, source, correction=correction, large_print=large_print
    )
    assert before == [exercise.model_dump_json() for exercise in source]


def test_extra_material_row_refuses_even_when_headers_repeat(tmp_path):
    source = sources(rows=24, wrapped=True)
    extra = changed(source, extra_row=True)
    path = tmp_path / "extra.pdf"
    render(path, extra)
    with pytest.raises(ValueError, match=r"[Cc]ell|tableau|ligne"):
        llm_pdf.validate_llm_pdf(path, source, correction=False)


@pytest.mark.parametrize(
    "policy", [f"fr-nsi-v36-model-review-v{i}" for i in range(1, 6)]
)
def test_retained_policy_cells_still_validate(tmp_path, policy):
    from Backend.Core.france import rendering
    from Backend.Core.render_transaction import render_pdf_atomically

    source = sources()
    path = tmp_path / "retained.pdf"
    render_pdf_atomically(
        path,
        lambda destination: rendering.render_assessment(
            destination,
            source,
            correction=False,
            print_policy=policy,
            human_readable_graph_titles=True,
            coherent_material_flow=True,
        ),
        role="question_paper",
        language="fr-FR",
    )
    llm_pdf.validate_llm_pdf(path, source, correction=False, print_policy=policy)


def test_question_label_in_context_or_table_does_not_end_material_region(tmp_path):
    raw = [exercise.model_dump(mode="json") for exercise in sources()]
    raw[0]["context"] = "i 1. Une expérience de lecture des données."
    raw[0]["materials"][0]["rows"][1][0] = "1."
    source = [
        validate_authored_exercise(item, str(index))
        for index, item in enumerate(raw, 1)
    ]
    path = tmp_path / "labels.pdf"
    render(path, source)
    import pymupdf

    with pymupdf.open(path) as document:
        assert (
            sum(
                word[4] == "1." and abs(word[0] - 82) < 0.5
                for page in document
                for word in page.get_text("words")
            )
            >= 4
        )
    llm_pdf.validate_llm_pdf(path, source, correction=False)


@pytest.fixture(scope="module")
def ruled_source(tmp_path_factory):
    import pymupdf

    source = sources(rows=30, wrapped=True)
    path = tmp_path_factory.mktemp("ruled") / "source.pdf"
    render(path, source)
    with pymupdf.open(path) as document:
        yield source, list(document)


@pytest.mark.parametrize(
    "mutation",
    [
        "header",
        "vertical",
        "horizontal",
        "partial_vertical",
        "partial_horizontal",
        "collapsed",
        "repeated_header",
        "extra_grid",
        "glyph_boundary",
    ],
)
def test_missing_partial_ambiguous_or_corrupt_material_grid_refuses(
    ruled_source, mutation
):
    import pymupdf

    from Backend.Core.france import table_pdf
    from Backend.Core.france.whole_case_pdf import _heading

    source, pages = ruled_source
    starts = [
        next(
            index
            for index, page in enumerate(pages)
            if page.search_for(_heading(exercise))
        )
        for exercise in source
    ]
    material_pages = [
        index
        for index in range(starts[0], starts[1])
        if any(
            drawing.get("fill") and drawing["rect"].width > 400
            for drawing in pages[index].get_drawings()
        )
    ]
    target = material_pages[1 if mutation == "repeated_header" else 0]
    drawings = deepcopy(pages[target].get_drawings())
    header_index = next(
        index
        for index, drawing in enumerate(drawings)
        if drawing.get("fill") and drawing["rect"].width > 400
    )
    header = pymupdf.Rect(drawings[header_index]["rect"])
    vertical = next(
        index
        for index, drawing in enumerate(drawings)
        if drawing["items"][0][0] == "l"
        and drawing["rect"].width == 0
        and abs(drawing["rect"].x0 - (header.x0 + header.width / 2)) < 1
    )
    horizontal = next(
        index
        for index, drawing in enumerate(drawings)
        if drawing["items"][0][0] == "l"
        and drawing["rect"].height == 0
        and drawing["rect"].y0 > header.y1
    )
    if mutation == "header":
        drawings.pop(header_index)
    elif mutation in {"vertical", "horizontal"}:
        drawings.pop(vertical if mutation == "vertical" else horizontal)
    elif mutation in {"partial_vertical", "partial_horizontal", "collapsed"}:
        index = vertical if mutation != "partial_horizontal" else horizontal
        first, last = drawings[index]["items"][0][1:]
        if mutation == "partial_vertical":
            first = pymupdf.Point(first.x, first.y - 3)
        elif mutation == "partial_horizontal":
            first = pymupdf.Point(first.x + 3, first.y)
        else:
            first, last = (
                pymupdf.Point(header.x0 + 0.2, first.y),
                pymupdf.Point(header.x0 + 0.2, last.y),
            )
        drawings[index]["items"] = [("l", first, last)]
    elif mutation == "extra_grid":
        drawings.append(deepcopy(drawings[header_index]))

    class ChangedPage:
        def __getattr__(self, name):
            return getattr(pages[target], name)

        def get_drawings(self):
            return drawings

        def get_text(self, mode):
            result = deepcopy(pages[target].get_text(mode))
            if mode == "rawdict" and mutation in {"repeated_header", "glyph_boundary"}:
                chars = [
                    char
                    for block in result["blocks"]
                    for line in block.get("lines", [])
                    for span in line["spans"]
                    for char in span["chars"]
                    if header.contains(pymupdf.Rect(char["bbox"]))
                    and not char["c"].isspace()
                ]
                if mutation == "repeated_header":
                    chars[0]["c"] = "X"
                else:
                    box = pymupdf.Rect(chars[0]["bbox"])
                    box.x0, box.x1 = (
                        header.x0 + header.width / 2 - 2,
                        header.x0 + header.width / 2 + 2,
                    )
                    chars[0]["bbox"] = tuple(box)
            return result

    changed_pages = list(pages)
    changed_pages[target] = ChangedPage()
    tables = [
        [
            (llm_pdf._table_label(exercise, material), material)
            for material in exercise.materials
            if material.kind == "table"
        ]
        for exercise in source
    ]
    with pytest.raises(
        ValueError, match=r"[Cc]ell|tableau|colonne|ligne|Glyphe|Grille|Limites"
    ):
        anchors = [
            (page, pages[page].search_for(llm_pdf._heading(exercise))[0].y1)
            for page, exercise in zip(starts, source, strict=True)
        ]
        table_pdf.check_material_tables(changed_pages, source, anchors, tables)
