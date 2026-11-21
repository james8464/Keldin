from pathlib import Path

import pytest
from aqaaccountgen.cli import _LIVE_ADAPTER

from Backend.Core import assessment_package
from Backend.Core.ai_assessment import (
    _app_owned_choice_credit_point,
    _tasks,
    _validate_checkpoint_item,
)


@pytest.fixture
def accounting_paper_and_syllabus():
    syllabus = _LIVE_ADAPTER.load_syllabus(
        Path("Resources/accounting/aqa/generator/data/syllabus.json")
    )
    paper = _LIVE_ADAPTER.build(_LIVE_ADAPTER.load_rule("1"), syllabus, 26080100)
    return paper, syllabus


@pytest.fixture
def selected_response_task(accounting_paper_and_syllabus):
    paper, syllabus = accounting_paper_and_syllabus
    return next(
        task
        for task in _tasks(paper, {topic.id: topic for topic in syllabus.topics})
        if task.question.number == "05"
    )


def _candidate(task, prompt):
    choices = [
        "The business uses more debt relative to its equity",
        "The business uses more equity relative to its debt",
        "The business cuts its current borrowings substantially",
        "The business returns inventory to its supplier",
    ]
    awarded = _app_owned_choice_credit_point(task.question, choices[0])
    return task.question.model_copy(
        update={
            "prompt": prompt,
            "choices": choices,
            "correct_choice": 0,
            "mark_scheme": [awarded.text],
            "structured_mark_scheme": [awarded],
        }
    )


def test_checkpoint_will_not_readmit_a_stem_that_repeats_its_key(
    selected_response_task,
):
    task = selected_response_task
    copied = _candidate(
        task,
        "Which statement is true? The business uses more debt relative to its equity.",
    )
    with pytest.raises(ValueError, match="prompt repeats its correct choice"):
        _validate_checkpoint_item(task, copied)


@pytest.mark.parametrize(
    "prompt",
    [
        "Which statement correctly describes higher gearing?",
        "Which argument applies? The business uses more debt relative to its equity; "
        "the business uses more equity relative to its debt.",
    ],
)
def test_checkpoint_keeps_distinct_stems_and_balanced_given_claims(
    selected_response_task, prompt
):
    task = selected_response_task
    _validate_checkpoint_item(task, _candidate(task, prompt))


def test_live_writer_refuses_a_stem_that_discloses_the_key(
    accounting_paper_and_syllabus, selected_response_task, tmp_path
):
    paper, _ = accounting_paper_and_syllabus
    task = selected_response_task
    section_index, option_index, question_index = task.key
    paper.sections[section_index].options[option_index].questions[question_index] = (
        _candidate(
            task,
            "Which statement is true? The business uses more debt relative to its equity.",
        )
    )
    path = tmp_path / "must-not-publish.json"
    with pytest.raises(ValueError, match="prompt repeats its correct choice"):
        assessment_package.write_assessment_package(
            paper,
            path,
            subject="accounting_aqa",
            paper_number="1",
            preview=False,
            provider="fixture",
            model="fixture",
        )
    assert not path.exists()
