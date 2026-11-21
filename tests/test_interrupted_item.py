"""Local control: a remote quota interruption must not lose validated work."""

import pytest

from Backend.Core.ai_assessment import (
    GenerationPolicy,
    _generate_batch,
    _Task,
    regenerate_generic_paper_item,
)
from Backend.Core.assessment_checkpoints import (
    AssessmentCheckpointStore,
    DeferredCheckpoints,
)
from Backend.Core.exam_blueprints import (
    GeneratedOption,
    GeneratedQuestion,
    MarkSchemePoint,
)
from Backend.Core.whole_paper_review import PaperFinding
from tests.support.solver_responses import complete_solver_response
from tests.test_ai_assessment import (
    _demand_profile,
    _difficulty_response,
    _question_response,
    _review_response,
)
from tests.test_assessment_checkpoints import (
    FirstPassDifficultyClient,
    NoCallsClient,
    identity,
    paper_fixture,
)


@pytest.mark.parametrize("resume", ["same", "corrupt", "changed", "after_difficulty"])
def test_difficulty_interruption_resumes_without_drafting_or_reviewing_again(
    tmp_path, resume
):
    point = MarkSchemePoint(
        text="Link the consequence to the case.", marks=1, assessment_objective="AO1"
    )
    question = GeneratedQuestion(
        rule_id="q1",
        number="1",
        marks=1,
        kind="data_response",
        command_word="Explain",
        topic_id="topic",
        prompt="Explain one effect using the supplied case.",
        mark_scheme=[point.text],
        structured_mark_scheme=[point],
        assessment_objectives={"AO1": 1},
        intended_demand="standard",
    )
    task = _Task(
        key=(0, 0, 0),
        question=question,
        option=GeneratedOption(
            id="case", title="Case", stimulus=["Costs changed."], questions=[question]
        ),
        topic=type(
            "Topic", (), {"id": "topic", "title": "Business change", "points": []}
        )(),
    )
    checkpoint = tmp_path / "assessment.json"
    store_identity = identity(model="fixture").model_copy(update={"provider": "openai"})

    class Client:
        provider = "openai"
        model = "fixture"

        def __init__(self, *, interrupted):
            self.interrupted = interrupted
            self.operations = []

        def generate_request(self, request):
            self.operations.append(request.operation)
            if request.operation == "authoring":
                return _question_response(
                    task.id,
                    "Explain one effect of higher costs using the supplied case.",
                )
            if request.operation == "solver":
                text = "The stated change affects the outcome through a relevant causal relationship."
                return complete_solver_response({"answer": text, "mark_points": [text]})
            if request.operation == "batch_review":
                return _review_response(task.id, approved=True)
            assert request.operation == "difficulty"
            if self.interrupted:
                raise RuntimeError("simulated free quota cutoff")
            return _difficulty_response(approved=True, demand="standard", steps=2)

    def run(client, store, *, subject="Economics"):
        return _generate_batch(
            [task],
            client=client,
            subject=subject,
            seed=123,
            progress=None,
            policy=GenerationPolicy(
                attempts=1,
                require_independent_solution=True,
                require_difficulty_review=True,
            ),
            checkpoint_store=store,
            demand_profile=_demand_profile(),
        )

    store = AssessmentCheckpointStore(checkpoint, store_identity)
    first = Client(interrupted=resume != "after_difficulty")
    if first.interrupted:
        with pytest.raises(RuntimeError, match="simulated free quota cutoff"):
            run(first, DeferredCheckpoints(store))
    else:
        # Simulate a stop between a complete item and durable batch admission.
        run(first, DeferredCheckpoints(store))
    assert first.operations == ["authoring", "solver", "batch_review", "difficulty"]
    assert store.load_item(task.id) is None

    second = Client(interrupted=False)
    reopened = AssessmentCheckpointStore(checkpoint, store_identity)
    if resume == "corrupt":
        key = f"item-stage-v1:{task.id}:authoring"
        stored = reopened.load_payload(key)
        assert stored is not None
        reopened.save_payload(key, {**stored, "response": {"questions": []}})
    subject = "Business" if resume == "changed" else "Economics"
    result = run(second, reopened, subject=subject)[task.key]
    assert result.authoring_context["difficulty_evidence"]["approved"] is True
    assert reopened.load_item(task.id) == result
    expected = {
        "same": ["difficulty"],
        "corrupt": ["authoring", "difficulty"],
        "changed": ["authoring", "batch_review", "difficulty"],
        "after_difficulty": [],
    }
    assert second.operations == expected[resume]


def test_paper_repair_can_resume_before_its_required_paper_rereview(tmp_path):
    paper, rule, topics = paper_fixture()
    item_id = "1@sections.0.options.0.questions.0"
    original = paper.sections[0].options[0].questions[0]
    finding = PaperFinding(
        kind="credit_mismatch",
        target_id=item_id,
        peer_id=item_id,
        target_quote=original.prompt,
        peer_quote=original.mark_scheme[0],
        reason="The key does not say which reasoning earns credit.",
    )
    path = tmp_path / "repair.json"

    def repair(client):
        return regenerate_generic_paper_item(
            paper,
            paper,
            item_id=item_id,
            findings=(finding,),
            rule=rule,
            syllabus_topics=topics,
            syllabus_topic_ids={"topic"},
            client=client,
            subject="Economics",
            policy=GenerationPolicy(attempts=1, require_difficulty_review=True),
            demand_profile=_demand_profile(),
            progress=None,
            stage_store=AssessmentCheckpointStore(path, identity()),
        )

    first = repair(
        FirstPassDifficultyClient(operations=["explain", "analyse", "contextualise"])
    )
    restored = repair(NoCallsClient())
    assert restored == first and restored != paper
    # The repair has not passed the paper-wide re-review and must not replace
    # the accepted question in the ordinary item slot.
    store = AssessmentCheckpointStore(path, identity())
    assert store.load_item("0/0/0") is None
    assert store.load_payload("item-stage-v1:whole-paper-repair:0/0/0:difficulty")
