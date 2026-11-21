import json

import pytest

from Backend.Core import whole_paper_review as review
from Backend.Core.assessment_checkpoints import AssessmentCheckpointStore
from tests.test_assessment_checkpoints import identity


def _oversized_items():
    return (
        review.ReviewItem(
            "1",
            "Explain the financial effect.",
            " ".join(
                f"Credit {index}: state the documented effect." for index in range(370)
            ),
        ),
        review.ReviewItem(
            "2", "Compare the statements.", "Credit a supported comparison."
        ),
    )


def test_oversized_uk_paper_uses_bounded_staged_review_and_resumes(tmp_path):
    items = _oversized_items()
    with pytest.raises(ValueError, match="budget"):
        review._review_windows(items)
    staged = review._within_item_windows(items) + review._cross_item_windows(items)
    assert len(staged) > 1
    path = tmp_path / "checkpoints.json"

    class Reviewer:
        def __init__(self, limit=None):
            self.limit = limit
            self.payloads = []

        def generate_request(self, request):
            if len(self.payloads) == self.limit:
                raise RuntimeError("simulated free quota cutoff")
            raw = request.prompt.rsplit("\n", 1)[1]
            assert isinstance(json.loads(raw)["references"], list)
            assert len(raw.encode()) <= review._REQUEST_BYTES
            self.payloads.append(raw)
            return {"findings": []}

    def run(client):
        return review.review_and_repair_paper(
            items,
            client,
            repair=lambda *_: pytest.fail("No defect was reported."),
            window_checkpoint=AssessmentCheckpointStore(path, identity()),
        )

    first = Reviewer(limit=1)
    with pytest.raises(RuntimeError, match="simulated free quota cutoff"):
        run(first)
    resumed = Reviewer()
    assert run(resumed).items == items
    assert first.payloads + resumed.payloads == [window.payload for window in staged]


def test_staged_review_does_not_cache_an_unbound_reference(tmp_path):
    path = tmp_path / "checkpoints.json"

    class Reviewer:
        def generate_request(self, _request):
            return {
                "findings": [
                    {
                        "kind": "credit_mismatch",
                        "target_ref": "P999.1",
                        "peer_ref": "K1.1",
                        "reason": "There is no such question in this request.",
                    }
                ]
            }

    with pytest.raises(ValueError, match="reference"):
        review.review_and_repair_paper(
            _oversized_items(),
            Reviewer(),
            repair=lambda *_: pytest.fail("Invalid evidence."),
            window_checkpoint=AssessmentCheckpointStore(path, identity()),
        )
    assert not path.exists()


def test_a_transport_failure_does_not_switch_to_staged_review():
    class Reviewer:
        def __init__(self):
            self.calls = 0

        def generate_request(self, request):
            self.calls += 1
            assert isinstance(json.loads(request.prompt.rsplit("\n", 1)[-1]), list)
            raise RuntimeError("Provider unavailable")

    client = Reviewer()
    with pytest.raises(RuntimeError, match="Provider unavailable"):
        review.review_and_repair_paper(
            (
                review.ReviewItem(
                    "1", "Explain the effect.", "Credit supported reasoning."
                ),
            ),
            client,
            repair=lambda *_: pytest.fail("No validated finding."),
        )
    assert client.calls == 1
