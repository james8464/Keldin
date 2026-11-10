"""The mark scheme prints declared credit policy, never tariff-invented bands."""

from __future__ import annotations

import re
import unicodedata

import pymupdf
import pytest
from cspapergen.generator import build_paper1_blueprint, build_paper2_blueprint
from cspapergen.render_pdf import render_mark_scheme
from cspapergen.syllabus import load_syllabus

from Backend.Core.open_credit import printed_credit_points


def normalise(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def rendered_text(blueprint, path):
    before = blueprint.model_dump_json()
    render_mark_scheme(blueprint, path)
    assert blueprint.model_dump_json() == before
    with pymupdf.open(path) as document:
        assert all(page.get_text().strip() for page in document)
        return normalise(" ".join(page.get_text() for page in document))


def assert_declared_credit(blueprint, text):
    for question in blueprint.questions:
        for part in question.parts:
            for point in printed_credit_points(part.marking.model_dump(mode="json")):
                assert normalise(point) in text
            for accepted in part.marking.accept:
                assert normalise(f"A. {accepted}") in text
            for rejected in part.marking.reject:
                assert normalise(f"R. {rejected}") in text
            for level in part.marking.levels:
                assert normalise(level) in text


@pytest.fixture(scope="module", params=[270100, 20, 123])
def point_scheme(request, tmp_path_factory):
    blueprint, _context = build_paper1_blueprint(load_syllabus(), seed=request.param)
    assert all(not part.marking.levels for q in blueprint.questions for part in q.parts)
    path = tmp_path_factory.mktemp(f"cs-point-policy-{request.param}") / "scheme.pdf"
    return blueprint, path, rendered_text(blueprint, path)


def test_point_only_scheme_does_not_invent_holistic_bands(point_scheme):
    _blueprint, _path, text = point_scheme
    assert "Mark range" not in text
    assert "Complete, logically structured solution" not in text
    assert "Level of response marking instructions" not in text
    assert "assessed holistically" not in text
    assert "Point-based marking instructions" in text


def test_all_declared_points_questions_marks_and_reference_solutions_survive(
    point_scheme,
):
    blueprint, _path, text = point_scheme
    assert [q.number for q in blueprint.questions] == list(range(1, 13))
    assert sum(part.marks for q in blueprint.questions for part in q.parts) == 100
    assert_declared_credit(blueprint, text)
    for number in (4, 9, 10, 11, 12):
        assert f"Question {number:02d}: Example Python 3 solution" in text
    assert "Completed adjacency matrix" in text
    assert "visited on entry" in text


@pytest.mark.parametrize("paper", ["1", "2"])
def test_explicit_declared_levels_are_preserved_without_invented_bands(paper, tmp_path):
    syllabus = load_syllabus()
    blueprint = (
        build_paper1_blueprint(syllabus, seed=270100)[0]
        if paper == "1"
        else build_paper2_blueprint(syllabus, seed=270100)
    )
    target = (
        next(
            part
            for question in blueprint.questions
            for part in question.parts
            if part.marking.ao == "AO3" and part.marks >= 7
        )
        if paper == "1"
        else blueprint.questions[0].parts[0]
    )
    target.marking.levels = [
        "Mark range: apply this source-owned descriptor and its stated allocation."
    ]
    target.marking.accept.append("Technically equivalent source-owned route.")
    target.marking.reject.append("A response contradicting the declared contract.")
    text = rendered_text(blueprint, tmp_path / f"declared-{paper}.pdf")
    assert_declared_credit(blueprint, text)
    assert "Level of response marking instructions" in text
    assert "only to parts with explicitly declared levels" in text
    assert (
        "For every other part, use its stated creditworthy points and allocations"
        in text
    )
    assert "Complete, logically structured solution" not in text
    assert normalise(target.marking.levels[0]) in text
