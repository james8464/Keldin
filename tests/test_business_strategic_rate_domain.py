"""Owned public strategic-change rate admission, without model inference."""

from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from Backend.Core.subjects.selected_response import (
    selected_response_contract,
    solve_selected_response,
)


def test_business_shared_case_tables_follow_printed_question_ownership():
    from aqabizgen.cli import ADAPTER

    from Backend.Core.assessment_package import whole_paper_review_items

    syllabus = ADAPTER.load_syllabus(
        Path("Resources/business/aqa/generator/data/syllabus.json")
    )
    paper = ADAPTER.build(ADAPTER.load_rule("1"), syllabus, 26080100)
    items = {
        item.id.split("@", 1)[0]: item
        for item in whole_paper_review_items(
            paper, subject="business_aqa", paper_number="1"
        )
    }
    figure = "\n".join(items["06"].context)
    assert "unscaled axes" in figure
    for label in ("M:", "N:", "TR1:", "TC1:", "TR2:", "TC2:"):
        assert label in figure
    assert "fixed_cost_before" not in figure
    assert "variable_cost_after" not in figure
    for question in ("16", "17"):
        text = "\n".join(items[question].context)
        assert "Extract from accounts of" in text
        assert "Net current assets" in text
        assert "Total equity" in text
        assert "capital employed" not in text.casefold()
        assert "Average span of control" not in text
        assert "Suppliers have also warned" not in text
    assert "Average span of control | 5 | 15" in items["18"].context
    assert "Net current assets" not in "\n".join(items["18"].context)
    for question in ("19", "20"):
        assert "Before restructuring | After restructuring" not in "\n".join(
            items[question].context
        )
        assert "Extract from accounts of" not in "\n".join(items[question].context)


@pytest.mark.parametrize("paper_number", ["2", "3"])
def test_business_case_charts_and_booklet_tables_are_owned_by_the_case(paper_number):
    from aqabizgen.cli import ADAPTER

    from Backend.Core.assessment_package import whole_paper_review_items

    syllabus = ADAPTER.load_syllabus(
        Path("Resources/business/aqa/generator/data/syllabus.json")
    )
    paper = ADAPTER.build(ADAPTER.load_rule(paper_number), syllabus, 26080100)
    items = whole_paper_review_items(
        paper, subject="business_aqa", paper_number=paper_number
    )
    case = paper.sections[0].options[0]
    label, value = case.chart_labels[0], case.chart_values[0]
    assert all(
        f"{label}: {value:.1f}" in item.context
        for item in items
        if item.id.split("@", 1)[1].startswith("sections.0.options.0.questions.")
    )
    if paper_number == "2":
        assert f"Market value and {case.title} sales (index values)" in items[0].context
        later_title = paper.sections[1].options[0].chart_title
        assert later_title not in items[0].context
    else:
        assert "Employee engagement | 55% | 58% | 60%" in items[0].context
        assert "Capacity utilisation | 70% | 74% | 72%" in items[0].context


def test_business_whole_paper_review_only_receives_its_printed_financial_inputs():
    from Backend.Core.assessment_package import whole_paper_review_items
    from Backend.Core.whole_paper_review import ReviewedPaper

    finance = {
        "number": "07",
        "prompt": "Calculate the profit for the year.",
        "marks": 1,
        "choices": ["11", "53", "7", "13"],
        "correct_choice": 0,
        "authoring_context": {
            "selected_response_contract": selected_response_contract(
                "after_tax_profit",
                inputs={
                    "revenue": "53",
                    "cost_of_sales": "29",
                    "operating_expenses": "7",
                    "taxation": "6",
                    "private": "Unprinted source sentinel",
                },
            )
        },
    }
    adjacent = {
        "number": "08",
        "prompt": "Define profit.",
        "marks": 1,
        "mark_scheme": ["Remaining revenue after costs."],
    }
    paper = {
        "sections": [
            {
                "options": [
                    {"questions": [finance]},
                    {"questions": [adjacent]},
                ]
            }
        ]
    }

    def review():
        return whole_paper_review_items(paper, subject="business_aqa", paper_number="1")

    original = review()
    assert original[0].context == (
        "Financial data | £m",
        "Sales revenue | 53",
        "Cost of sales | 29",
        "Operating expenses | 7",
        "Taxation | 6",
    )
    assert original[1].context == ()
    previous = whole_paper_review_items(
        paper, subject="business_aqa", paper_number="1", policy="whole-paper-review-v2"
    )
    assert previous[0].context == ()
    finance["authoring_context"]["selected_response_contract"]["inputs"]["taxation"] = (
        "8"
    )
    changed = review()
    assert changed[1] == original[1]
    assert ReviewedPaper(changed, ()).receipt() != ReviewedPaper(original, ()).receipt()


def item(external, strategic):
    return {
        "kind": "multiple_choice",
        "marks": 1,
        "choices": [
            "Strategic fit",
            "Strategic drift",
            "Tactical planning",
            "Diversification",
        ],
        "authoring_context": {
            "selected_response_contract": selected_response_contract(
                "strategic_drift",
                inputs={"external_change": external, "strategic_change": strategic},
            )
        },
    }


@pytest.mark.parametrize(
    "value", ["not-a-rate", "medium", "17", Decimal("17"), "", " high", "low "]
)
@pytest.mark.parametrize("placement", ["both", "external", "strategic"])
def test_unsupported_public_rate_refuses_without_mutating_input(value, placement):
    question = item(
        value if placement in {"both", "external"} else "high",
        value if placement in {"both", "strategic"} else "low",
    )
    original = deepcopy(question)
    with pytest.raises(ValueError, match="unsupported strategic-change classification"):
        solve_selected_response(question)
    assert question == original


@pytest.mark.parametrize(
    "external,strategic,answer",
    [
        ("high", "low", "Strategic drift"),
        ("high", "high", "Strategic fit"),
        ("low", "low", "Strategic fit"),
        ("HIGH", "Low", "Strategic drift"),
        ("HiGh", "HIGH", "Strategic fit"),
        ("LOW", "LoW", "Strategic fit"),
    ],
)
def test_supported_rate_pairs_keep_their_existing_results(external, strategic, answer):
    question = item(external, strategic)
    original = deepcopy(question)
    result = solve_selected_response(question)
    assert result["answer"] == answer
    assert result["mark_points"] == [answer]
    assert result["numeric_results"] == {}
    assert question == original


def test_reverse_supported_movement_still_refuses():
    question = item("low", "high")
    original = deepcopy(question)
    with pytest.raises(ValueError, match="unsupported strategic-change classification"):
        solve_selected_response(question)
    assert question == original


@pytest.mark.parametrize("mutation", ["missing", "extra", "rows", "format"])
def test_existing_contract_shape_refusals_remain(mutation):
    question = item("high", "low")
    contract = question["authoring_context"]["selected_response_contract"]
    if mutation == "missing":
        del contract["inputs"]["external_change"]
    elif mutation == "extra":
        contract["inputs"]["unrelated"] = "high"
    elif mutation == "rows":
        contract["rows"] = [{"label": "Unrelated"}]
    else:
        contract["decimal_places"] = 1
    original = deepcopy(question)
    with pytest.raises(ValueError):
        solve_selected_response(question)
    assert question == original
