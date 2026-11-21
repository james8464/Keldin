from pathlib import Path

import pytest
from aqaaccountgen import cli
from aqaaccountgen.cli import _LIVE_ADAPTER, ADAPTER
from aqaaccountgen.configs import RULES
from aqaaccountgen.generator import build_paper
from aqaaccountgen.syllabus import load_syllabus

from Backend.Core.ai_assessment import _independently_validate_candidate, _tasks
from Backend.Core.exam_blueprints import app_owns_choice_credit
from Backend.Core.independent_solver import IndependentSolver
from tests.support.solver_responses import complete_solver_response


def test_public_and_credit_contract_changes_have_a_new_accounting_identity():
    assert ADAPTER.prompt_version == "ai-assessment-v17-accounting-prime-entry"
    assert (
        _LIVE_ADAPTER.prompt_version == "ai-assessment-v19-accounting-ratio-terminology"
    )


@pytest.mark.parametrize(
    ("preview", "expected"), [(True, ADAPTER), (False, _LIVE_ADAPTER)]
)
def test_accounting_credit_is_selected_only_for_live_generation(
    monkeypatch, tmp_path, preview, expected
):
    def run(adapter, *, dry_run, **_):
        assert adapter is expected
        assert dry_run is preview
        return {}

    monkeypatch.setattr(cli, "run_family_adapter", run)
    cli.generate_package(
        paper="1",
        syllabus_path=tmp_path / "spec.json",
        output_dir=tmp_path,
        dry_run=preview,
    )


@pytest.mark.parametrize(
    ("paper_id", "model_written"),
    [
        ("paper_1", {"02", "03", "05", "10"}),
        ("paper_2", {"01", "02", "03", "07", "08", "09", "10"}),
    ],
)
def test_only_unlocked_accounting_choices_use_app_owned_credit(paper_id, model_written):
    syllabus = load_syllabus(
        Path(__file__).resolve().parents[1]
        / "Resources/accounting/aqa/generator/data/syllabus.json"
    )
    topics = {topic.id: topic for topic in syllabus.topics}
    preview = ADAPTER.build(RULES[paper_id], syllabus, 270100)
    live = _LIVE_ADAPTER.build(RULES[paper_id], syllabus, 270100)
    assert not any(
        app_owns_choice_credit(task.question) for task in _tasks(preview, topics)
    )
    live_tasks = _tasks(live, topics)
    assert {
        task.question.number
        for task in live_tasks
        if app_owns_choice_credit(task.question)
    } == model_written
    for task in live_tasks:
        task.question.authoring_context.pop("app_owned_choice_credit", None)
    live_raw, preview_raw = [paper.model_dump(mode="json") for paper in (live, preview)]
    if paper_id == "paper_1":
        live_first, preview_first = [
            paper["sections"][0]["options"][0]["questions"][0]
            for paper in (live_raw, preview_raw)
        ]
        assert live_first["number"] == preview_first["number"] == "01"
        assert live_first["topic_id"] == preview_first["topic_id"] == "accounting-3"
        assert (
            live_first["assessment_objectives"]
            == preview_first["assessment_objectives"]
        )
        assert (
            live_first["authoring_context"]["selected_response_contract"]["operation"]
            == "prime_entry_book"
        )
        public = {
            k: v
            for k, v in live_first.items()
            if k not in {"mark_scheme", "structured_mark_scheme", "correct_choice"}
        }
        assert (
            IndependentSolver().solve(public, []).answer
            == live_first["choices"][live_first["correct_choice"]]
        )
        live_raw["sections"][0]["options"][0]["questions"][0] = preview_first
        live_questions, preview_questions = [
            paper["sections"][0]["options"][0]["questions"]
            for paper in (live_raw, preview_raw)
        ]
        assert live_questions[3]["number"] == preview_questions[3]["number"] == "04"
        assert live_questions[3]["topic_id"] == preview_questions[3]["topic_id"]
        assert (
            live_questions[3]["assessment_objectives"]
            == preview_questions[3]["assessment_objectives"]
        )
        live_questions[3] = preview_questions[3]
    assert live_raw == preview_raw


def test_live_q04_derives_both_liquidity_definitions_without_a_draft_key():
    syllabus = load_syllabus(
        Path("Resources/accounting/aqa/generator/data/syllabus.json")
    )
    topics = {topic.id: topic for topic in syllabus.topics}
    selected = set()
    for seed in range(18):
        paper = _LIVE_ADAPTER.build(RULES["paper_1"], syllabus, seed)
        q = next(t.question for t in _tasks(paper, topics) if t.question.number == "04")
        assert q.prompt != "Which ratio measures short-term liquidity?"
        assert q.topic_id == "accounting-8"
        assert q.marks == 1
        assert q.authoring_context["preserve_prompt"] is True
        assert q.authoring_context["selected_response_contract"]["operation"] == (
            "liquidity_ratio_definition"
        )
        public = q.model_dump(
            exclude={"correct_choice", "mark_scheme", "structured_mark_scheme"}
        )
        answer = IndependentSolver().solve(public, []).answer
        assert answer == q.choices[q.correct_choice]
        selected.add(answer)
    assert selected == {"Current ratio", "Liquid capital ratio (acid test ratio)"}


@pytest.mark.parametrize("key", ["accounting_source_content", "grouped_level_policy"])
def test_blind_solver_never_receives_accounting_private_credit(key):
    prompts = []

    class Client:
        def generate_json(self, prompt):
            prompts.append(prompt)
            return complete_solver_response(
                {
                    "answer": "Public reasoning",
                    "steps": ["Use public facts."],
                    "mark_points": ["Public reasoning"],
                }
            )

    IndependentSolver(Client()).solve(
        {
            "id": "private-accounting-canary",
            "kind": "explain",
            "marks": 6,
            "assessment_objectives": {"AO1": 6},
            "prompt": "Explain two reasons for using control accounts.",
            "authoring_context": {
                key: {"text": "PRIVATE_CREDIT_CANARY"},
                "source_data": {
                    "credit": "PUBLIC_CREDIT_COLUMN",
                    "nested": [
                        {key: {"text": "NESTED_CREDIT_CANARY"}, "public": "PUBLIC_FACT"}
                    ],
                },
            },
        },
        [],
    )
    assert len(prompts) == 1
    assert "PRIVATE_CREDIT_CANARY" not in prompts[0]
    assert "NESTED_CREDIT_CANARY" not in prompts[0]
    assert "PUBLIC_CREDIT_COLUMN" in prompts[0]
    assert "PUBLIC_FACT" in prompts[0]


@pytest.mark.parametrize(
    "key",
    ["accounting_source_content", "grouped_level_policy", "accounting_marking_policy"],
)
def test_changed_private_credit_policy_is_rejected_before_model_use(key):
    syllabus = load_syllabus(
        Path(__file__).resolve().parents[1]
        / "Resources/accounting/aqa/generator/data/syllabus.json"
    )
    paper = build_paper(RULES["paper_1"], syllabus, 270100)
    task = next(
        task
        for task in _tasks(paper, {topic.id: topic for topic in syllabus.topics})
        if task.question.number == "11"
    )
    candidate = task.question.model_copy(deep=True)
    candidate.authoring_context[key] = "PRIVATE_REPLACEMENT"

    class Client:
        def generate_json(self, _prompt):
            raise AssertionError("changed private marking contract reached the model")

    with pytest.raises(ValueError, match="immutable numeric source contract"):
        _independently_validate_candidate(task, candidate, client=Client())
