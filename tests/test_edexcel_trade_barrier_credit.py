"""Task-specific knowledge without changing source facts or existing tariffs."""

import hashlib
import json
from pathlib import Path

import pytest
from pastpapergen import credit_contracts, generator
from pastpapergen.assessment_contracts import objective_budget
from pastpapergen.extended_scenarios import concrete_fallback
from pastpapergen.paper_configs import load_builtin_paper_config
from pastpapergen.syllabus import load_syllabus

ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT / "Resources/economics/edexcel-a/generator"
TRADE_KNOWLEDGE = (
    "A trade barrier restricts cross-border exchange, unlike a domestic transaction cost.",
    "A tariff is a tax on imports; reducing it lowers the tax-inclusive import price, other things equal.",
)


def paper(number, seed):
    assert Path(generator.__file__).resolve() == FAMILY / "pastpapergen/generator.py"
    assert (
        Path(credit_contracts.__file__).resolve()
        == FAMILY / "pastpapergen/credit_contracts.py"
    )
    return generator.build_paper_blueprint(
        load_builtin_paper_config(f"paper_{number}"),
        load_syllabus(FAMILY / "data/syllabus_seed.json"),
        seed,
    )


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def trade_question(marks):
    # Direct binder control over the existing owned scenario, not a new live route.
    original = next(q for q in paper(2, 0).questions if q.number == "6(b)")
    return concrete_fallback(
        original.model_copy(
            update={
                "marks": marks,
                "mark_scheme": [
                    "Correctly identifies or defines the relevant concept."
                ],
            }
        )
    )


def test_actual_paper_two_seed_zero_eight_mark_task_has_trade_knowledge():
    question = next(q for q in paper(2, 0).questions if q.number == "6(b)")
    assert question.marks == 8 and question.topic_id == "4.1"
    assert "reduction in trade barriers" in question.prompt
    assert "lower tariffs" in question.source_text
    assert question.assessment_objectives == {"AO1": 2, "AO2": 2, "AO3": 2, "AO4": 2}
    knowledge = [p for p in question.mark_scheme if p.startswith("AO1")]
    assert knowledge == [f"AO1 (1 mark): {point}" for point in TRADE_KNOWLEDGE]
    assert not any("appreciation" in point.casefold() for point in knowledge)


@pytest.mark.parametrize("marks", [5, 8])
def test_direct_trade_credit_preserves_input_source_and_point_budgets(marks):
    question = trade_question(marks)
    before = question.model_dump(mode="json")
    budget = objective_budget(marks, question.command_word)
    scheme, contract = credit_contracts.extended_credit(question, budget)
    assert question.model_dump(mode="json") == before
    assert scheme is contract["credit"]
    assert [p for p in scheme if p.startswith("AO1")] == [
        f"AO1 (1 mark): {point}" for point in TRADE_KNOWLEDGE
    ]
    assert sum(budget.values()) == marks
    assert contract["scheme_mode"] == "points"
    for ao in ("AO1", "AO2"):
        assert sum(p.startswith(f"{ao} (1 mark):") for p in scheme) == 2
    if marks == 8:
        assert contract["kaa_marks"] == 6 and contract["evaluation_marks"] == 2
        assert sum(p.startswith("AO3 (1 mark):") for p in scheme) == 2


@pytest.mark.parametrize(
    ("marks", "expected"),
    [
        (5, "ecb65b94f529773d647990bf2835446fe5caa134ab31eb1c326eeaaee349ceca"),
        (10, "a9395a46939b125f47f18c4c0ae89af7eb15e7135db3237ca97af1597fe7691c"),
        (12, "827b8616072715a39f875f41d13a2de5a2ea47edf6c1fc9c5cd2fed6fdba450d"),
        (15, "b7782832217190f2a04c39dd1dde764e2cbda754dffa8581425aee1d6b4f1093"),
        (25, "4e0f7526ee68e05c5e8e542b6278eb4c12bb599dbcae66590b9f1070954723b9"),
    ],
)
def test_existing_five_and_higher_tariffs_are_byte_identical(marks, expected):
    question = trade_question(marks)
    budget = objective_budget(marks, question.command_word)
    result = credit_contracts.extended_credit(question, budget)
    assert digest(result) == expected  # Captured from the pre-repair source.
    assert sum(budget.values()) == marks
    if marks >= 10:
        assert result[1]["scheme_mode"] == "levels"
        assert result[1]["kaa_marks"] + result[1]["evaluation_marks"] == marks


def test_existing_actual_four_mark_part_and_authored_eight_routes_are_unchanged():
    question = next(q for q in paper(2, 0).questions if q.number == "2")
    part = next(p for p in question.parts if p.label == "b")
    assert part.marks == 4 and sum(part.assessment_objectives.values()) == 4
    assert digest(part.model_dump(mode="json")) == (
        "c7c275a6c6c33a111f986e3fd72fd15dc82ed42aeb357d65c37019e41ebfc477"
    )
    authored = next(q for q in paper(3, 1).questions if q.number == "1(b)")
    assert authored.marks == 8 and authored.topic_id == "3.1"
    assert digest(authored.assessment_contract) == (
        "82c2a072834769cbee8f6a2fc972dca64cc58fefce19301c35ac1186adb026e4"
    )


def test_direct_currency_concept_control_retains_original_knowledge():
    # Helper-only control: this is not asserted to be a current seeded currency task.
    question = trade_question(8).model_copy(
        update={"prompt": "Examine two effects of a domestic currency appreciation."}
    )
    scheme, _ = credit_contracts.extended_credit(
        question, objective_budget(8, question.command_word)
    )
    assert [p for p in scheme if p.startswith("AO1")] == [
        f"AO1 (1 mark): {point}" for point in credit_contracts.KNOWLEDGE_FACTS["4.1"]
    ]


def test_one_argument_knowledge_lookup_keeps_original_contract():
    for topic, expected in credit_contracts.KNOWLEDGE_FACTS.items():
        assert credit_contracts._knowledge_pair(topic) == expected
