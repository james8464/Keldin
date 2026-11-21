import json
from importlib import import_module
from itertools import combinations

import pytest


def _controller():
    try:
        return import_module("Backend.Core.whole_paper_review")
    except ModuleNotFoundError as error:
        if error.name != "Backend.Core.whole_paper_review":
            raise
        pytest.fail("The pre-export whole-paper review controller is missing.")


class ScriptedReviewer:
    def __init__(self, *verdicts):
        self.verdicts = iter(verdicts)
        self.prompts = []

    def generate_json(self, prompt):
        self.prompts.append(prompt)
        return next(self.verdicts)


def _items(controller):
    return (
        controller.ReviewItem("1", "Name the sorting algorithm.", "Merge sort"),
        controller.ReviewItem(
            "2", "The algorithm from question 1 is merge sort.", "Four"
        ),
    )


def _leakage(quote):
    return {
        "findings": [
            {
                "kind": "answer_leakage",
                "target_id": "2",
                "peer_id": "1",
                "target_quote": quote,
                "peer_quote": "Merge sort",
                "reason": "Question 2 supplies the answer to question 1.",
            }
        ]
    }


@pytest.mark.parametrize("reference_evidence", [False, True])
def test_repairs_an_answer_disclosed_by_its_own_context(reference_evidence):
    controller = _controller()
    original = controller.ReviewItem(
        "1",
        "State the precondition for binary search.",
        "The index must be ordered by identifier.",
        context=("The index is already ordered by identifier.",),
    )
    revised = controller.ReviewItem(
        original.id,
        original.prompt,
        original.mark_scheme,
        context=("The library maintains an identifier index.",),
    )
    evidence = (
        {"target_ref": "C1.1", "peer_ref": "K1.1"}
        if reference_evidence
        else {
            "target_id": original.id,
            "peer_id": original.id,
            "target_quote": original.context[0],
            "peer_quote": original.mark_scheme,
        }
    )
    reviewer = ScriptedReviewer(
        {
            "findings": [
                {
                    "kind": "self_answer_leakage",
                    **evidence,
                    "reason": "The stem supplies the condition the question asks for.",
                }
            ]
        },
        {"findings": []},
    )
    result = controller.review_and_repair_paper(
        (original,),
        reviewer,
        repair=lambda item, findings: revised,
        reference_evidence=reference_evidence,
    )
    assert result.items == (revised,)
    assert result.repaired_ids == (original.id,)
    assert len(reviewer.prompts) == 2


@pytest.mark.parametrize("reference_evidence", [False, True])
@pytest.mark.parametrize("wrong_source", ["own_option", "other_key"])
def test_self_leakage_cannot_repair_from_wrong_evidence(
    reference_evidence, wrong_source
):
    controller = _controller()
    items = (
        controller.ReviewItem(
            "1",
            "Which planet is nearest the Sun?",
            "Mercury",
            context=("Mercury is nearest the Sun.",)
            if wrong_source == "other_key"
            else (),
            options=("Mercury", "Venus", "Earth", "Mars"),
        ),
        controller.ReviewItem("2", "Which planet has rings?", "Saturn"),
    )
    if reference_evidence:
        evidence = (
            {"target_ref": "O1.1", "peer_ref": "K1.1"}
            if wrong_source == "own_option"
            else {"target_ref": "C1.1", "peer_ref": "K2.1"}
        )
    else:
        evidence = (
            {
                "target_id": "1",
                "peer_id": "1",
                "target_quote": "Mercury",
                "peer_quote": "Mercury",
            }
            if wrong_source == "own_option"
            else {
                "target_id": "1",
                "peer_id": "2",
                "target_quote": items[0].context[0],
                "peer_quote": "Saturn",
            }
        )
    reviewer = ScriptedReviewer(
        {
            "findings": [
                {"kind": "self_answer_leakage", **evidence, "reason": "Invalid source."}
            ],
        }
    )
    with pytest.raises(ValueError, match="source evidence"):
        controller.review_and_repair_paper(
            items,
            reviewer,
            repair=lambda *_: pytest.fail("Wrong evidence must not trigger repair"),
            reference_evidence=reference_evidence,
        )


def test_quoted_review_cannot_cite_an_item_outside_its_request():
    controller = _controller()
    items = tuple(
        controller.ReviewItem(str(i), f"Question {i} prompt", f"Key {i} " + "x" * 4200)
        for i in range(3)
    )
    reviewer = ScriptedReviewer(
        {
            "findings": [
                {
                    "kind": "answer_leakage",
                    "target_id": "0",
                    "peer_id": "2",
                    "target_quote": "Question 0 prompt",
                    "peer_quote": "Key 2",
                    "reason": "This key was not included in the first window.",
                }
            ]
        },
        {"findings": []},
        {"findings": []},
    )

    with pytest.raises(ValueError, match="source evidence"):
        controller.review_and_repair_paper(
            items,
            reviewer,
            repair=lambda *_: pytest.fail(
                "Unpresented evidence cannot trigger repairs."
            ),
        )
    assert '"id": "2"' not in reviewer.prompts[0]


def test_staged_review_repairs_and_reviews_the_same_item_again():
    controller = _controller()
    original = controller.ReviewItem(
        "1",
        "Name the sorting method.",
        "Merge sort.",
        context=("The method is merge sort.",),
    )
    revised = controller.ReviewItem(
        "1",
        original.prompt,
        original.mark_scheme,
        context=("A divide-and-conquer approach is used.",),
    )
    reviewer = ScriptedReviewer(
        {
            "findings": [
                {
                    "kind": "self_answer_leakage",
                    "target_ref": "C1.1",
                    "peer_ref": "K1.1",
                    "reason": "The given context states the answer.",
                }
            ]
        },
        {"findings": []},
    )

    result = controller.review_and_repair_paper(
        (original,),
        reviewer,
        repair=lambda *_: revised,
        staged_evidence=True,
    )

    assert result.items == (revised,)
    assert len(reviewer.prompts) == 2
    assert original.context[0] in reviewer.prompts[0]
    assert revised.context[0] in reviewer.prompts[1]
    assert original.context[0] not in reviewer.prompts[1]


def test_apple_staged_review_resolves_numbered_evidence_and_rechecks_changed_item():
    from Backend.Core.apple_intelligence import solver_schema_mode

    controller = _controller()
    original = controller.ReviewItem(
        "1",
        "Name the sorting method.",
        "Merge sort.",
        context=("The method is merge sort.",),
    )
    repaired = controller.ReviewItem(
        "1",
        original.prompt,
        original.mark_scheme,
        context=("The method divides a list into smaller lists.",),
    )
    evidence = []

    class AppleReviewer:
        provider = "apple_intelligence"

        def generate_request(self, request):
            assert (
                solver_schema_mode(request.operation, request.schema)
                == "guided_with_postvalidation"
            )
            rows = json.loads(request.prompt.rsplit("\n", 1)[-1])["references"]
            refs = {field: int(next(iter(aliases))) for field, _, aliases in rows}
            evidence.append(rows)
            return {
                "findings": [
                    {
                        "kind": "self_answer_leakage",
                        "target_ref": refs["context"],
                        "peer_ref": refs["mark_scheme"],
                        "reason": "The context states the answer.",
                    }
                ]
                if len(evidence) == 1
                else []
            }

    def repair(item, findings):
        assert item == original
        assert findings[0].target_quote == original.context[0]
        assert findings[0].peer_quote == original.mark_scheme
        return repaired

    result = controller.review_and_repair_paper(
        (original,), AppleReviewer(), repair=repair, staged_evidence=True
    )
    assert result.items == (repaired,)
    assert result.repaired_ids == ("1",)
    assert len(evidence) == 2


@pytest.mark.parametrize(
    "invalid_reference", ["absent", "boolean", "choice", "wrong_kind"]
)
def test_apple_staged_review_rejects_invalid_numbered_evidence(invalid_reference):
    controller = _controller()
    item = controller.ReviewItem(
        "1",
        "Name the sorting method.",
        "Merge sort.",
        context=("The method is merge sort.",),
        options=("Merge sort", "Bubble sort"),
    )

    class AppleReviewer:
        provider = "apple_intelligence"

        def generate_request(self, request):
            rows = json.loads(request.prompt.rsplit("\n", 1)[-1])["references"]
            refs = {field: int(next(iter(aliases))) for field, _, aliases in rows}
            target = {
                "absent": max(refs.values()) + 1,
                "boolean": True,
                "choice": refs["options"],
                "wrong_kind": refs["prompt"],
            }[invalid_reference]
            return {
                "findings": [
                    {
                        "kind": "contradiction"
                        if invalid_reference == "wrong_kind"
                        else "self_answer_leakage",
                        "target_ref": target,
                        "peer_ref": refs["mark_scheme"],
                        "reason": "This claim does not have admissible evidence.",
                    }
                ]
            }

    def repair(*_):
        pytest.fail("An invalid citation must not trigger a repair.")

    with pytest.raises(ValueError):
        controller.review_and_repair_paper(
            (item,), AppleReviewer(), repair=repair, staged_evidence=True
        )


def test_staged_review_refuses_a_cross_question_finding_during_own_item_review():
    controller = _controller()
    reviewer = ScriptedReviewer(
        {
            "findings": [
                {
                    "kind": "answer_leakage",
                    "target_ref": "P2.1",
                    "peer_ref": "K1.1",
                    "reason": "The second question exposes the first answer.",
                }
            ]
        }
    )
    with pytest.raises(ValueError, match="wrong stage"):
        controller.review_and_repair_paper(
            _items(controller),
            reviewer,
            repair=lambda *_: pytest.fail("Do not repair a wrong-stage finding."),
            staged_evidence=True,
        )


def test_repairs_only_the_flagged_item_and_reviews_the_changed_pair():
    controller = _controller()
    reviewer = ScriptedReviewer(_leakage("merge sort"), {"findings": []})
    items = _items(controller)

    def repair(item, findings):
        assert item.id == "2" and findings[0].peer_id == "1"
        return controller.ReviewItem("2", "How many values are present?", "Four")

    result = controller.review_and_repair_paper(items, reviewer, repair=repair)
    assert result.items == (
        items[0],
        controller.ReviewItem("2", "How many values are present?", "Four"),
    )
    assert len(reviewer.prompts) == 2
    assert "How many values are present?" in reviewer.prompts[1]
    assert "Name the sorting algorithm." in reviewer.prompts[1]


def test_rejects_a_finding_with_no_matching_source_evidence():
    controller = _controller()
    reviewer = ScriptedReviewer(_leakage("invented passage"))

    def repair(*_):
        pytest.fail("Unverified reports must not trigger regeneration.")

    with pytest.raises(ValueError, match="evidence"):
        controller.review_and_repair_paper(_items(controller), reviewer, repair=repair)


def test_same_clue_reported_twice_repairs_only_the_leaking_item():
    controller = _controller()
    clue = "Merge sort is the answer to question 1."
    items = (
        controller.ReviewItem("1", "Name the sorting algorithm.", "Merge sort."),
        controller.ReviewItem("2", clue + " Explain a queue’s purpose.", "FIFO."),
    )
    raw = _leakage(clue)
    raw["findings"].append(
        {
            "kind": "duplicate_demand",
            "target_id": "1",
            "peer_id": "2",
            "target_quote": "Name the sorting algorithm.",
            "peer_quote": clue + " Explain a queue's purpose.",
            "reason": "These are distinct concepts but the second refers to the answer.",
        }
    )
    revised = controller.ReviewItem("2", "Explain a queue’s purpose.", "FIFO.")
    reviewer = ScriptedReviewer(raw, {"findings": []})

    def repair(item, findings):
        assert item.id == "2"
        assert tuple(finding.kind for finding in findings) == ("answer_leakage",)
        return revised

    result = controller.review_and_repair_paper(items, reviewer, repair=repair)
    assert result.items == (items[0], revised)
    assert result.repaired_ids == ("2",)


def test_distinct_duplicate_evidence_is_not_hidden_by_a_leak():
    controller = _controller()
    clue = "Merge sort is the answer to question 1."
    items = (
        controller.ReviewItem("1", "Name the sorting algorithm.", "Merge sort."),
        controller.ReviewItem(
            "2", clue + " Name the sorting algorithm.", "Merge sort."
        ),
    )
    raw = _leakage(clue)
    raw["findings"].append(
        {
            "kind": "duplicate_demand",
            "target_id": "2",
            "peer_id": "1",
            "target_quote": "Name the sorting algorithm.",
            "peer_quote": "Name the sorting algorithm.",
            "reason": "Both prompts separately ask the same question.",
        }
    )
    reviewer = ScriptedReviewer(raw, {"findings": []})

    def repair(item, findings):
        assert tuple(finding.kind for finding in findings) == (
            "answer_leakage",
            "duplicate_demand",
        )
        return controller.ReviewItem(item.id, "State a use for a stack.", "Undo.")

    controller.review_and_repair_paper(items, reviewer, repair=repair)


@pytest.mark.parametrize("peer_ref", ["K1.1", "K2.1"])
def test_addressed_review_resolves_exact_ownership_without_model_quotes(peer_ref):
    controller = _controller()
    draft = {
        "findings": [
            {
                "kind": "answer_leakage",
                "target_ref": "P2.1",
                "peer_ref": peer_ref,
                "reason": "The second prompt gives away the sorting algorithm.",
            }
        ],
    }
    reviewer = ScriptedReviewer(draft, {"findings": []})
    items = _items(controller)
    revised = controller.ReviewItem("2", "Explain a queue’s purpose.", "Four")

    def repair(item, findings):
        assert item.id == "2"
        assert findings[0].peer_id == "1"
        assert findings[0].peer_quote == "Merge sort"
        assert findings[0].target_quote == items[1].prompt
        return revised

    if peer_ref == "K2.1":
        with pytest.raises(ValueError, match="source evidence"):
            controller.review_and_repair_paper(
                items, reviewer, repair=repair, reference_evidence=True
            )
        return
    result = controller.review_and_repair_paper(
        items, reviewer, repair=repair, reference_evidence=True
    )
    assert result.items == (items[0], revised)


def test_reference_schema_cannot_assign_a_prompt_to_the_answer_key_role():
    from jsonschema import Draft202012Validator

    controller = _controller()
    items = _items(controller)
    revised = controller.ReviewItem("2", "Explain a queue’s purpose.", "Four")

    class SchemaReviewer:
        def generate_request(self, request):
            if "Explain a queue’s purpose." in request.prompt:
                return {"findings": []}
            finding = {
                "kind": "answer_leakage",
                "target_ref": "P2.1",
                "peer_ref": "K1.1",
                "reason": "The visible clue gives away the correct answer.",
            }
            validator = Draft202012Validator(request.schema)
            assert validator.is_valid({"findings": [finding]})
            assert not validator.is_valid(
                {"findings": [{**finding, "peer_ref": "P1.1"}]}
            )
            assert not validator.is_valid(
                {"findings": [{**finding, "peer_ref": "K99.1"}]}
            )
            assert not validator.is_valid(
                {"findings": [{**finding, "peer_ref": "K2.1"}]}
            )
            assert validator.is_valid(
                {
                    "findings": [
                        {**finding, "kind": "credit_mismatch", "peer_ref": "K2.1"}
                    ]
                }
            )
            return {"findings": [finding]}

    reviewed = controller.review_and_repair_paper(
        items,
        SchemaReviewer(),
        repair=lambda _item, _: revised,
        reference_evidence=True,
    )
    assert reviewed.repaired_ids == ("2",)


def test_distinguishes_the_leaking_question_from_the_answer_key_owner():
    controller = _controller()
    raw = _leakage("merge sort")
    raw["findings"][0].update(target_id="1", peer_id="2", peer_quote="Four")
    reviewer = ScriptedReviewer(raw)
    with pytest.raises(ValueError, match="source evidence: target quote belongs"):
        controller.review_and_repair_paper(
            _items(controller), reviewer, repair=lambda item, _: item
        )


def test_large_review_covers_each_item_pair_without_truncation():
    controller = _controller()
    items = tuple(
        controller.ReviewItem(str(i), f"Question {i}", f"Evidence {i}: " + "x" * 4200)
        for i in range(3)
    )
    reviewer = ScriptedReviewer(*({"findings": []} for _ in range(3)))

    def repair(*_):
        pytest.fail("A clean paper should not be changed.")

    result = controller.review_and_repair_paper(items, reviewer, repair=repair)
    assert result.items == items and result.repaired_ids == ()
    payloads = [json.loads(prompt.rsplit("\n", 1)[-1]) for prompt in reviewer.prompts]
    assert {tuple(row["id"] for row in payload) for payload in payloads} == set(
        combinations(("0", "1", "2"), 2)
    )
    for payload in payloads:
        assert all(
            row["mark_scheme"] == items[int(row["id"])].mark_scheme for row in payload
        )


def test_paper_that_exceeds_both_plans_refuses_before_dispatch(monkeypatch):
    controller = _controller()
    monkeypatch.setattr(controller, "_REQUEST_BYTES", 420)
    items = tuple(
        controller.ReviewItem(str(i), f"Question {i}", "x" * 11_000) for i in range(2)
    )
    reviewer = ScriptedReviewer()
    with pytest.raises(ValueError, match="budget"):
        controller.review_and_repair_paper(items, reviewer, repair=lambda item, _: item)
    assert not reviewer.prompts


def test_single_oversized_item_cannot_pass_without_review():
    controller = _controller()
    items = (controller.ReviewItem("1", "Explain the result.", "x" * 13_000),)
    reviewer = ScriptedReviewer({})
    with pytest.raises(ValueError, match="findings"):
        controller.review_and_repair_paper(items, reviewer, repair=lambda item, _: item)
    assert len(reviewer.prompts) == 1


def test_within_item_plan_covers_every_source_to_credit_pair():
    controller = _controller()
    items = (
        controller.ReviewItem(
            "1",
            "Explain the primary effect.",
            "\n".join(f"Credit {i}: " + "a" * 200 for i in range(65)),
            ("Référence " * 850,),
            ("Distractor", "Correct option"),
            15,
        ),
        controller.ReviewItem("2", "Name the method.", "Record the method.", marks=1),
    )
    _, expected_refs = controller._addressed_payload(items)
    assert len(controller._addressed_payload(items[:1])[0].encode()) > 12_000

    windows = controller._within_item_windows(items)

    seen = {}
    actual_pairs = set()
    for window in windows:
        assert len(window.payload.encode()) <= 12_000
        seen.update(window.references)
        visible = {
            ref
            for ref, source in window.references.items()
            if source.field != "mark_scheme"
        }
        keys = {
            ref
            for ref, source in window.references.items()
            if source.field == "mark_scheme"
        }
        actual_pairs.update(
            (clue, key)
            for clue in visible
            for key in keys
            if window.references[clue].item_id == window.references[key].item_id
        )
    assert seen == expected_refs
    assert actual_pairs == {
        (clue, key)
        for clue, visible in expected_refs.items()
        if visible.field != "mark_scheme"
        for key, credit in expected_refs.items()
        if credit.field == "mark_scheme"
        if visible.item_id == credit.item_id
    }


def test_within_item_plan_batches_short_items_without_permitting_cross_item_findings():
    from jsonschema import Draft202012Validator

    controller = _controller()
    items = tuple(
        controller.ReviewItem(str(i), "Explain the effect.", "A worked answer.")
        for i in range(1, 8)
    )
    (window,) = controller._within_item_windows(items)
    assert window.payload.count("A worked answer.") == 1
    validator = Draft202012Validator(window.schema)

    def finding(kind, key):
        return {
            "findings": [
                {
                    "kind": kind,
                    "target_ref": "P1.1",
                    "peer_ref": key,
                    "reason": "Concrete cited evidence.",
                }
            ]
        }

    assert validator.is_valid(finding("credit_mismatch", "K1.1"))
    assert not validator.is_valid(finding("credit_mismatch", "K2.1"))
    assert not validator.is_valid(finding("answer_leakage", "K2.1"))


def test_cross_item_plan_covers_each_relevant_pair_within_byte_budget():
    controller = _controller()
    items = tuple(
        controller.ReviewItem(
            str(i),
            f"Prompt for question {i}. " * 120,
            f"Answer for question {i}. " * 160,
            (f"Context for question {i}. " * 100,),
            ("The first option.", "The second option."),
        )
        for i in range(3)
    )
    _, refs = controller._addressed_payload(items)
    windows = controller._cross_item_windows(items)
    for window in windows:
        assert len(window.payload.encode()) <= 12_000
        assert "self_answer_leakage" not in window.kinds

    for kind in ("answer_leakage", "duplicate_demand", "contradiction"):

        def relevant(first, second, kind=kind):
            return first.item_id != second.item_id and (
                (first.field != "mark_scheme" and second.field == "mark_scheme")
                if kind == "answer_leakage"
                else first.field == second.field == "prompt"
            )

        expected = {
            (a, b)
            for a, first in refs.items()
            for b, second in refs.items()
            if relevant(first, second)
        }
        actual = {
            (a, b)
            for w in windows
            if kind in w.kinds
            for a, first in w.references.items()
            for b, second in w.references.items()
            if relevant(first, second)
        }
        assert expected and actual == expected


def test_addressed_repeated_source_is_sent_once_without_losing_owners():
    controller = _controller()
    source = "Source excerpt: all devices use copper wiring."
    items = (
        controller.ReviewItem("1", "Explain a suitable cable.", "Copper", (source,)),
        controller.ReviewItem(
            "2", "Describe a cable property.", "Conductivity", (source,)
        ),
    )

    payload, references = controller._addressed_payload(items)

    rows = json.loads(payload)
    assert payload.count(source) == 1
    assert rows[0]["context"]["C1.1"] == source
    assert rows[1]["context"]["C2.1"] == {"same_text_as": "C1.1"}
    assert (references["C1.1"].item_id, references["C2.1"].item_id) == ("1", "2")
    assert references["C1.1"].text == references["C2.1"].text == source


def test_common_candidate_source_is_sent_once_per_window():
    controller = _controller()
    source = "Relevant source text " + "x" * 4500
    items = tuple(
        controller.ReviewItem(str(i), f"Question {i}", f"Answer {i}", context=(source,))
        for i in range(4)
    )
    reviewer = ScriptedReviewer({"findings": []})
    result = controller.review_and_repair_paper(
        items, reviewer, repair=lambda item, _: item
    )
    assert result.items == items
    assert len(reviewer.prompts) == 1 and reviewer.prompts[0].count(source) == 1
    payload = json.loads(reviewer.prompts[0].rsplit("\n", 1)[-1])
    assert all(
        row["context"] == [{"item_id": "0", "context_index": 0}] for row in payload[1:]
    )


def test_projection_keeps_candidate_context_choices_key_and_allocated_marks():
    from Backend.Core import assessment_package

    project = getattr(assessment_package, "whole_paper_review_items", None)
    assert project is not None, "review must use the same marked items as export"
    blueprint = {
        "sections": [
            {
                "options": [
                    {
                        "stimulus": ["The firm reports a 10% rise in sales."],
                        "questions": [
                            {
                                "number": "01",
                                "topic_id": "business",
                                "prompt": "Using the extract, which measure increased?",
                                "marks": 1,
                                "choices": ["Cost", "Sales"],
                                "correct_choice": 1,
                                "mark_scheme": ["Award one mark for option B."],
                            }
                        ],
                    }
                ]
            }
        ],
    }
    (item,) = project(blueprint, subject="business_aqa", paper_number="1")

    assert item.id == "01@sections.0.options.0.questions.0"
    assert item.prompt == "Using the extract, which measure increased?"
    assert item.context == ("The firm reports a 10% rise in sales.",)
    assert item.options == ("A. Cost", "B. Sales")
    assert "B. Sales" in item.mark_scheme
    assert "Award one mark for option B." in item.mark_scheme
    assert item.marks == 1


def test_review_projection_keeps_credit_without_duplicate_plain_rows():
    from Backend.Core.assessment_package import whole_paper_review_items

    answer = "Net profit fell despite higher revenue."
    row = {
        "text": answer,
        "marks": 2,
        "assessment_objective": "AO2",
        "alternatives": ["Higher costs outweighed sales growth."],
        "allow": [],
        "do_not_accept": ["Revenue declined."],
        "depends_on": ["row-1"],
    }
    quote = 'Accept "retained profit" where relevant.'
    quoted_row = {**row, "text": quote, "marks": 0}
    standalone = "A valid conclusion must use the source."
    blueprint = {
        "questions": [
            {
                "number": "01",
                "topic_id": "business",
                "prompt": "Explain the reported result.",
                "marks": 2,
                "mark_scheme": [answer, quote, standalone],
                "structured_mark_scheme": [row, quoted_row],
            }
        ]
    }
    (item,) = whole_paper_review_items(
        blueprint, subject="business_aqa", paper_number="1"
    )
    *plain, encoded = item.mark_scheme.splitlines()
    assert plain == [quote, standalone]
    assert json.loads(encoded) == [
        {key: value for key, value in point.items() if value != []}
        for point in (row, quoted_row)
    ]


def test_interrupted_whole_paper_review_resumes_only_exact_completed_windows(tmp_path):
    from dataclasses import replace

    from Backend.Core.assessment_checkpoints import AssessmentCheckpointStore
    from tests.test_assessment_checkpoints import identity

    controller = _controller()
    items = tuple(
        controller.ReviewItem(str(index), f"Question {index} " + "a" * 4_400, "Key")
        for index in range(3)
    )
    assert len(controller._review_windows(items)) == 3
    successful = {"findings": []}

    class InterruptedReviewer(ScriptedReviewer):
        def generate_json(self, prompt):
            if self.prompts:
                raise RuntimeError("provider quota reached after first response")
            return super().generate_json(prompt)

    path = tmp_path / "paper-wide-review.json"
    first = InterruptedReviewer(successful)
    with pytest.raises(RuntimeError, match="provider quota"):
        controller.review_and_repair_paper(
            items,
            first,
            repair=lambda item, _: item,
            window_checkpoint=AssessmentCheckpointStore(path, identity()),
        )
    resumed = ScriptedReviewer(successful, successful)
    reviewed = controller.review_and_repair_paper(
        items,
        resumed,
        repair=lambda item, _: item,
        window_checkpoint=AssessmentCheckpointStore(path, identity()),
    )
    assert reviewed.items == items
    assert len(resumed.prompts) == 2
    assert first.prompts[0] not in resumed.prompts

    changed = (replace(items[0], prompt=items[0].prompt + " changed."), *items[1:])
    fresh = ScriptedReviewer(successful, successful)
    assert (
        controller.review_and_repair_paper(
            changed,
            fresh,
            repair=lambda item, _: item,
            window_checkpoint=AssessmentCheckpointStore(path, identity()),
        ).items
        == changed
    )
    assert len(fresh.prompts) == 2


@pytest.mark.parametrize("recovers", [True, False])
def test_standard_review_retries_malformed_uncached_verdict(tmp_path, recovers):
    from Backend.Core.assessment_checkpoints import AssessmentCheckpointStore
    from tests.test_assessment_checkpoints import identity

    controller = _controller()
    items = _items(controller)
    valid = _leakage("merge sort")
    malformed = {"findings": [dict(valid["findings"][0])]}
    finding = malformed["findings"][0]
    finding["type"] = finding.pop("kind")
    del finding["reason"]
    reviewer = ScriptedReviewer(
        malformed, valid if recovers else malformed, {"findings": []}
    )
    path = tmp_path / "paper-review.json"
    repaired = controller.ReviewItem("2", "Count the comparisons.", "Four")
    repairs = []

    def repair(item, findings):
        repairs.append((item.id, findings[0].kind))
        return repaired

    def review(client):
        return controller.review_and_repair_paper(
            items,
            client,
            repair=repair,
            window_checkpoint=AssessmentCheckpointStore(path, identity()),
        )

    if recovers:
        assert review(reviewer).items == (items[0], repaired)
        assert repairs == [("2", "answer_leakage")]
        assert len(reviewer.prompts) == 3
        repairs.clear()
        resumed = ScriptedReviewer()
        assert review(resumed).items == (items[0], repaired)
        assert not resumed.prompts
        assert repairs == [("2", "answer_leakage")]
    else:
        with pytest.raises(ValueError, match="Field required"):
            review(reviewer)
        assert len(reviewer.prompts) == 2
        assert not path.exists()
        assert not repairs
    assert reviewer.prompts[0] in reviewer.prompts[1]
    assert reviewer.prompts[0] != reviewer.prompts[1]


def test_unverified_paper_review_citation_is_not_checkpointed(tmp_path):
    from Backend.Core.assessment_checkpoints import AssessmentCheckpointStore
    from tests.test_assessment_checkpoints import identity

    controller = _controller()
    items = _items(controller)
    path = tmp_path / "paper-wide-review.json"
    with pytest.raises(ValueError, match="source evidence"):
        controller.review_and_repair_paper(
            items,
            ScriptedReviewer(_leakage("This text was never sent.")),
            repair=lambda item, _: item,
            window_checkpoint=AssessmentCheckpointStore(path, identity()),
        )
    assert not path.exists()


def test_multipart_repair_rereviews_its_siblings_together():
    controller = _controller()
    items = (
        controller.ReviewItem("1", "Name the sorting algorithm.", "Merge sort"),
        controller.ReviewItem(
            "2", "The algorithm from question 1 is merge sort.", "Four"
        ),
        controller.ReviewItem("2b", "Explain the running time.", "One key comparison."),
    )
    reviewer = ScriptedReviewer(_leakage("merge sort"), {"findings": []})
    edited = (
        controller.ReviewItem("2", "Describe the next step.", "Four"),
        controller.ReviewItem(
            "2b", "Explain the cost of the next step.", "One key comparison."
        ),
    )

    def repair(item, findings):
        assert item.id == "2" and findings[0].target_id == "2"
        return edited

    result = controller.review_and_repair_paper(
        items, reviewer, repair=repair, owner=lambda item_id: item_id.removesuffix("b")
    )
    assert result.items == (items[0], *edited)
    assert result.repaired_ids == ("2", "2b")
    assert "Explain the cost of the next step." in reviewer.prompts[1]


def test_french_review_counts_every_invalid_provider_dispatch(monkeypatch):
    from Backend.Core.france.generation_budget import FrenchGenerationBudget
    from Backend.Core.providers import HostedLLMClient

    controller = _controller()
    client = HostedLLMClient(provider="ollama", model="fixture", api_key="")
    attempts = []

    def invalid_reply(*_args, **options):
        attempts.append(options.get("french_nsi", False))
        raise ValueError("Invalid JSON")

    monkeypatch.setattr(client, "_ollama", invalid_reply)
    budget = FrenchGenerationBudget(client)
    with pytest.raises(ValueError, match="Invalid JSON"):
        controller.review_and_repair_paper(
            _items(controller),
            budget,
            repair=lambda item, _: item,
            french_transport=True,
        )
    assert attempts == [True]
    assert budget.snapshot()["started_requests"] == 1


@pytest.mark.parametrize("staged_evidence", [False, True])
@pytest.mark.parametrize(
    ("limit", "maximum"), [("MAX_REQUESTS", 2), ("MAX_RESERVED_OUTPUT_TOKENS", 2048)]
)
def test_french_review_plan_must_fit_all_remaining_calls(
    monkeypatch, staged_evidence, limit, maximum
):
    from Backend.Core.france import generation_budget

    controller = _controller()
    items = tuple(
        controller.ReviewItem(str(i), f"Question {i}", f"Credit {i}: " + "x" * 4200)
        for i in range(3)
    )

    class LocalReviewer:
        def generate_request(self, request):
            return {"findings": []}

    monkeypatch.setattr(generation_budget, limit, maximum)
    budget = generation_budget.FrenchGenerationBudget(LocalReviewer())
    with pytest.raises(generation_budget.GenerationLimitError, match="limite"):
        controller.review_and_repair_paper(
            items,
            budget,
            repair=lambda item, _: item,
            french_transport=True,
            staged_evidence=staged_evidence,
        )
    assert budget.snapshot()["started_requests"] == 0
    assert budget.snapshot()["reserved_output_tokens"] == 0


def test_french_oversized_item_uses_staged_review_without_dropping_evidence():
    from Backend.Core.france.generation_budget import FrenchGenerationBudget

    controller = _controller()
    long_context = " ".join(
        f"Équipe {index} retient le résultat de cette étape." for index in range(245)
    )
    items = (
        controller.ReviewItem(
            "E1/1", "Expliquer la règle.", "Donner la règle correcte.", (long_context,)
        ),
        controller.ReviewItem("E2/1", "Identifier la structure.", "Une file."),
    )
    requests = []

    class LocalReviewer:
        def generate_request(self, request):
            requests.append(request)
            return {"findings": []}

    budget = FrenchGenerationBudget(LocalReviewer())
    result = controller.review_and_repair_paper(
        items, budget, repair=lambda item, _: item, french_transport=True
    )
    assert result.items == items
    assert 1 < len(requests) == budget.snapshot()["started_requests"]
    assert all(request.operation == "french_nsi_authoring" for request in requests)
    assert all(
        len(request.prompt.split("\n", 1)[-1].encode()) <= 12_000
        for request in requests
    )
    packets = [json.loads(request.prompt.split("\n", 1)[-1]) for request in requests]
    sent = {
        text
        for packet in packets
        for field, text, _owners in packet["references"]
        if field == "context"
    }
    assert sent == {
        long_context[start : start + 240] for start in range(0, len(long_context), 240)
    }


def test_french_review_can_choose_a_smaller_complete_plan_before_dispatch(monkeypatch):
    from Backend.Core.france import generation_budget

    controller = _controller()
    items = tuple(
        controller.ReviewItem(
            f"E{i + 1}/1",
            f"Question {i}",
            "".join(f"{i:02d}{index:04d}" for index in range(2900 // 6)),
            ("Faits partagés." * 10,),
        )
        for i in range(5)
    )
    requests = []

    class LocalReviewer:
        def generate_request(self, request):
            requests.append(request)
            return {"findings": []}

    monkeypatch.setattr(generation_budget, "MAX_REQUESTS", 5)
    budget = generation_budget.FrenchGenerationBudget(LocalReviewer())
    result = controller.review_and_repair_paper(
        items, budget, repair=lambda item, _: item, french_transport=True
    )
    assert result.items == items
    assert len(requests) == budget.snapshot()["started_requests"] == 5
    assert all(
        "references" in json.loads(request.prompt.split("\n", 1)[-1])
        for request in requests
    )


def test_uk_export_receipt_verifies_exact_reviewed_content(tmp_path):
    from Backend.Core import assessment_package

    controller = _controller()
    path = tmp_path / "paper.json"
    args = dict(
        subject="fixture",
        paper_number="1",
        preview=False,
        provider="ollama",
        model="fixture",
    )
    blueprint = {
        "questions": [
            {
                "number": "1",
                "prompt": "State the capital of France.",
                "marks": 1,
                "mark_scheme": ["Award one mark for Paris."],
            }
        ]
    }
    items = assessment_package.whole_paper_review_items(
        blueprint, subject="fixture", paper_number="1"
    )
    assessed = controller.ReviewedPaper(items, (items[0].id,))
    assessment_package.write_assessment_package(
        blueprint,
        path,
        **args,
        whole_paper_review=assessed,
    )
    report = assessment_package.validate_assessment_package(
        path,
        **args,
        require_whole_paper_review=True,
    )
    assert report["whole_paper_review"]["repaired_ids"] == ["1@questions.0"]
    package = json.loads(path.read_text())
    package["whole_paper_review"]["reviewed_content_sha256"] = "0" * 64
    path.write_text(json.dumps(package))
    with pytest.raises(ValueError, match="review evidence"):
        assessment_package.validate_assessment_package(path, **args)
    package.pop("whole_paper_review")
    path.write_text(json.dumps(package))
    assessment_package.validate_assessment_package(path, **args)
    with pytest.raises(ValueError, match="review evidence"):
        assessment_package.validate_assessment_package(
            path, **args, require_whole_paper_review=True
        )
