"""Owned Edexcel numeric-source identity checks, with no inference or PDF changes."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pastpapergen.ollama_client import _question_solver_item
from pastpapergen.render_pdf import candidate_stimulus_data

from Backend.Core.subjects import economics_contracts
from Backend.Core.subjects.economics_contracts import solve_economics_contract
from tests.support.edexcel import forced_part


def test_supplied_diagram_is_bound_to_each_question_part_without_private_parameters():
    from pastpapergen.cli import ADAPTER

    from Backend.Core.assessment_package import whole_paper_review_items

    syllabus = ADAPTER.load_syllabus(
        Path("Resources/economics/edexcel-a/generator/data/syllabus_seed.json")
    )
    paper = ADAPTER.build(ADAPTER.load_rule("2"), syllabus, 26080119).assessment
    raw = paper.model_dump(mode="json")
    position = 3
    question = raw["questions"][position]
    question["stimulus_kind"] = "poverty_trap_diagram"
    question["graph_params"] = {"kind": "poverty_trap"}
    question["source_instance"]["kind"] = "poverty_trap_diagram"
    question["source_instance"]["context"] = "The caption identifies the plotted case."
    rows = [
        item
        for item in whole_paper_review_items(raw, subject="economics", paper_number="2")
        if item.id.split("@", 1)[1].startswith(f"questions.{position}.parts.")
    ]
    assert len(rows) == 2
    for item in rows:
        text = "\n".join(item.context)
        assert "The caption identifies the plotted case." in text
        assert (
            "Low income -> low savings -> low investment -> low productivity -> low income"
            in text
        )
        assert "parameters" not in text and "source_fingerprint" not in text


def test_every_rendered_edexcel_stimulus_diagram_has_visible_review_evidence():
    from pastpapergen.render_pdf import _GRAPH_FUNCS
    from pastpapergen.stimulus_diagrams import printed_diagram_review_context

    for kind in _GRAPH_FUNCS:
        context = printed_diagram_review_context(kind)
        assert len(context) >= 2, kind
        assert all(line.strip() for line in context), kind


def test_paper_three_review_matches_printed_figure_rows_and_merged_extracts():
    from pastpapergen.cli import ADAPTER

    from Backend.Core.assessment_package import whole_paper_review_items

    syllabus = ADAPTER.load_syllabus(
        Path("Resources/economics/edexcel-a/generator/data/syllabus_seed.json")
    )
    paper = ADAPTER.build(ADAPTER.load_rule("3"), syllabus, 26080120).assessment
    raw = paper.model_dump(mode="json")
    questions = raw["questions"]
    cell = questions[1]["source_instance"]["rows"][1][0]["text"]
    questions[1]["source_instance"]["source_id"] = "private-figure-provenance"
    items = {
        item.id.split("@", 1)[0]: item.context
        for item in whole_paper_review_items(raw, subject="economics", paper_number="3")
    }
    assert "Figure 1: illustrative case information" in items["1(a)"]
    assert "Figure 2: illustrative case information" in items["1(b)"]
    assert any(cell in line for line in items["1(b)"])
    assert not any(cell in line for line in items["1(c)"])
    assert all("private-figure-provenance" not in line for line in items["1(b)"])
    assert any(questions[0]["source_text"] in line for line in items["1(b)"])
    assert any(questions[1]["source_text"] in line for line in items["1(a)"])
    assert "Figure 3: illustrative case information" in items["2(a)"]
    assert not any("Figure 3" in line for line in items["2(b)"])
    assert any(questions[7]["source_text"] in line for line in items["2(b)"])


def test_edexcel_shared_extract_c_uses_the_same_question_for_print_and_review():
    from pastpapergen.cli import ADAPTER
    from pastpapergen.render_pdf import _extract_source_questions, _section_b_extracts

    from Backend.Core.assessment_package import whole_paper_review_items

    syllabus = ADAPTER.load_syllabus(
        Path("Resources/economics/edexcel-a/generator/data/syllabus_seed.json")
    )
    paper = ADAPTER.build(ADAPTER.load_rule("1"), syllabus, 26080100).assessment
    section_b = [question for question in paper.questions if question.section == "B"]
    section_b[2].source_text = "Wrong source for the extract C label."
    section_b[3].source_text = "Use the study of competing food suppliers."
    booklet = _extract_source_questions(section_b)
    inline = dict(_section_b_extracts(section_b))
    assert inline["Extract C"] == booklet[2].source_text == section_b[3].source_text
    items = whole_paper_review_items(paper, subject="economics", paper_number="1")
    explicit = next(item for item in items if item.id.startswith("6(d)@"))
    implicit = next(item for item in items if item.id.startswith("6(c)@"))
    expected = f"Extract C: {section_b[3].source_text}"
    assert expected in explicit.context
    assert expected in implicit.context
    assert section_b[2].source_text not in "\n".join(implicit.context)


def test_whole_paper_review_binds_printed_table_not_private_data():
    from Backend.Core.assessment_package import whole_paper_review_items
    from Backend.Core.whole_paper_review import ReviewedPaper

    question = forced_part("household_savings_line_chart", "calculate", 2)
    contract = question.model_dump(mode="json")
    source = contract["source_instance"]
    source["rows"] = [
        [{"text": "Period"}, {"text": "Import cost"}],
        [{"text": "March"}, {"number": "713.21", "unit": "GBP"}],
    ]
    source["values"] = []
    source["labels"] = []
    source["givens"] = {"freight_charge": {"number": "17.41", "unit": "GBP"}}
    source["source_id"] = "not printed source identifier"
    paper = {"paper_id": "paper_1", "questions": [contract]}

    def review():
        return whole_paper_review_items(paper, subject="economics", paper_number="1")

    original = review()
    context = "\n".join(original[0].context)
    assert all(
        label in context for label in ("Import cost", "March", "£713.21", "£17.41")
    )
    assert "not printed source identifier" not in context
    assert "source_fingerprint" not in context
    assert (
        whole_paper_review_items(
            json.loads(json.dumps(paper, sort_keys=True)),
            subject="economics",
            paper_number="1",
        )
        == original
    )
    previous = whole_paper_review_items(
        paper, subject="economics", paper_number="1", policy="whole-paper-review-v2"
    )
    assert "£713.21" not in "\n".join(previous[0].context)
    source["rows"][1][1]["number"] = "813.21"
    assert (
        ReviewedPaper(review(), ()).receipt() != ReviewedPaper(original, ()).receipt()
    )


def test_whole_paper_review_does_not_invent_a_candidate_drawn_figure():
    from Backend.Core.assessment_package import whole_paper_review_items

    question = forced_part("household_savings_line_chart", "calculate", 2)
    contract = question.model_dump(mode="json")
    contract["parts"][0]["command_word"] = "draw"
    contract["source_instance"]["rows"] = [[{"text": "Unprinted table token"}]]
    paper = {"paper_id": "paper_1", "questions": [contract]}
    (item,) = whole_paper_review_items(paper, subject="economics", paper_number="1")
    assert "Unprinted table token" not in "\n".join(item.context)


def projected_item(kind):
    root = Path(__file__).resolve().parents[1]
    for path in [
        economics_contracts.__file__,
        _question_solver_item.__code__.co_filename,
        candidate_stimulus_data.__code__.co_filename,
    ]:
        assert Path(path).resolve().is_relative_to(root)
    question = forced_part(kind, "calculate", 2)
    item = _question_solver_item(question, question.parts[0])
    assert item["stimulus"] == candidate_stimulus_data(question)
    return item


DESCRIPTORS = (
    "kind",
    "source_id",
    "source_fingerprint",
    "provenance",
    "x_label",
    "y_label",
)


def with_source_version(item, version):
    result = deepcopy(item)
    contract = result["authoring_context"]["economics_input_contract"]
    contract["source"]["version"] = version
    digest = hashlib.sha256(
        json.dumps(contract["source"], sort_keys=True).encode()
    ).hexdigest()
    contract["source_fingerprint"] = result["stimulus"]["source_fingerprint"] = digest
    return result


def test_valid_v2_source_has_the_same_canonical_answer():
    canonical = with_source_version(
        projected_item("household_savings_line_chart"), "edexcel-instance-v1"
    )
    current = with_source_version(canonical, "edexcel-instance-v2")
    before = deepcopy(current)
    assert solve_economics_contract(current) == solve_economics_contract(canonical)
    assert current == before


@pytest.mark.parametrize("field", DESCRIPTORS)
def test_changed_present_v1_descriptor_refuses(field):
    item = with_source_version(
        projected_item("household_savings_line_chart"), "edexcel-instance-v1"
    )
    item["stimulus"][field] = "Owned changed descriptor"
    before = deepcopy(item)
    try:
        with pytest.raises(ValueError, match="candidate source differs"):
            solve_economics_contract(item)
    finally:
        assert item == before


@pytest.mark.parametrize("field", DESCRIPTORS)
@pytest.mark.parametrize("mutation", ["changed", "missing"])
def test_v2_requires_every_descriptor(field, mutation):
    item = with_source_version(
        projected_item("household_savings_line_chart"), "edexcel-instance-v2"
    )
    if mutation == "missing":
        del item["stimulus"][field]
    else:
        item["stimulus"][field] = "Owned changed descriptor"
    before = deepcopy(item)
    try:
        with pytest.raises(ValueError, match="candidate source differs"):
            solve_economics_contract(item)
    finally:
        assert item == before


@pytest.mark.parametrize(
    "kind",
    [
        "household_savings_line_chart",
        "gdp_growth_bar_chart",
        "terms_of_trade_index_chart",
    ],
)
@pytest.mark.parametrize("field", ["x_label", "y_label"])
def test_changed_candidate_axis_refuses_without_mutating_either_projection(kind, field):
    item = projected_item(kind)
    item["stimulus"][field] = "Unrelated candidate-visible axis"
    before = deepcopy(item)
    try:
        with pytest.raises(ValueError, match="candidate source differs"):
            solve_economics_contract(item)
    finally:
        assert item == before


@pytest.mark.parametrize(
    "kind",
    [
        "household_savings_line_chart",
        "gdp_growth_bar_chart",
        "terms_of_trade_index_chart",
    ],
)
def test_current_canonical_projection_keeps_its_solution_and_bytes(kind):
    item = projected_item(kind)
    before = deepcopy(item)
    result = solve_economics_contract(item)
    assert result and result["answer"]
    assert item == before


@pytest.mark.parametrize(
    "kind",
    [
        "household_savings_line_chart",
        "gdp_growth_bar_chart",
        "terms_of_trade_index_chart",
    ],
)
def test_existing_v1_absent_axis_projection_remains_replayable(kind):
    item = with_source_version(projected_item(kind), "edexcel-instance-v1")
    assert (
        item["authoring_context"]["economics_input_contract"]["source"]["version"]
        == "edexcel-instance-v1"
    )
    canonical = solve_economics_contract(item)
    del item["stimulus"]["x_label"]
    del item["stimulus"]["y_label"]
    before = deepcopy(item)
    assert solve_economics_contract(item) == canonical
    assert item == before


@pytest.mark.parametrize("removed", [("provenance",), DESCRIPTORS])
def test_retained_v1_absent_descriptors_remain_accepted(removed):
    item = with_source_version(
        projected_item("household_savings_line_chart"), "edexcel-instance-v1"
    )
    original = solve_economics_contract(item)
    for field in removed:
        del item["stimulus"][field]
    before = deepcopy(item)
    assert solve_economics_contract(item) == original
    assert item == before


def test_new_factory_stamps_v2_but_default_and_explicit_v1_keep_their_identity():
    source = economics_contracts.EconomicsSource(source_id="owned-legacy", kind="owned")
    assert source.version == "edexcel-instance-v1"
    saved = source.model_dump_json().encode()
    loaded = economics_contracts.EconomicsSource.model_validate_json(saved)
    assert (
        loaded.version == source.version
        and loaded.fingerprint() == source.fingerprint()
    )
    assert loaded.model_dump_json().encode() == saved
    current = projected_item("household_savings_line_chart")
    assert (
        current["authoring_context"]["economics_input_contract"]["source"]["version"]
        == "edexcel-instance-v2"
    )


def test_retained_v1_blueprint_and_package_replay_without_rebinding(
    tmp_path, monkeypatch
):
    from pastpapergen import assessment_contracts
    from pastpapergen.generator import build_paper_blueprint
    from pastpapergen.models import PaperBlueprint
    from pastpapergen.paper_configs import load_builtin_paper_config
    from pastpapergen.syllabus import load_syllabus
    from pastpapergen.validation import validate_blueprint

    from Backend.Core.assessment_package import (
        validate_assessment_package,
        write_assessment_package,
    )

    root = Path(__file__).resolve().parents[1]
    config = load_builtin_paper_config("paper_2")
    syllabus = load_syllabus(
        root / "Resources/economics/edexcel-a/generator/data/syllabus_seed.json"
    )
    with monkeypatch.context() as legacy:
        legacy.setattr(
            assessment_contracts,
            "ECONOMICS_SOURCE_BINDING_VERSION",
            "edexcel-instance-v1",
        )
        original = build_paper_blueprint(config, syllabus, seed=26083122)
    saved = original.model_dump_json().encode()
    loaded = PaperBlueprint.model_validate_json(saved)
    validate_blueprint(loaded, config, syllabus)
    assert loaded.model_dump_json().encode() == saved
    for question in loaded.questions:
        assert question.source_instance.version == "edexcel-instance-v1"
        for part in question.parts:
            if part.command_word == "calculate":
                assert solve_economics_contract(_question_solver_item(question, part))
    path = tmp_path / "retained-v1.json"
    write_assessment_package(
        loaded,
        path,
        subject="economics",
        paper_number="2",
        preview=True,
        provider=None,
        model=None,
    )
    before = path.read_bytes()
    validate_assessment_package(
        path,
        subject="economics",
        paper_number="2",
        preview=True,
        provider=None,
        model=None,
    )
    assert path.read_bytes() == before
