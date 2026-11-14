import pytest

from Backend.Core.custom_assessment_contract import (
    DraftSection,
    PageCitation,
    confirm_custom_format,
    review_custom_format,
)
from Backend.Core.custom_assessment_evidence import (
    LocalDocumentEvidence,
    LocalPageEvidence,
)


def examples():
    return tuple(
        LocalDocumentEvidence(
            "question-paper", str(i) * 64, (LocalPageEvidence(1, f"Paper {i}"),)
        )
        for i in range(1, 4)
    )


def section(documents, **changes):
    return DraftSection.model_validate(
        {
            "id": "a",
            "title": "Section A",
            "question_count": 10,
            "answer_count": 8,
            "candidate_marks": 40,
            "formats": ["multiple-choice", "written"],
            "sources": [
                PageCitation(document_sha256=doc.sha256, page=1) for doc in documents
            ],
            **changes,
        }
    )


def test_review_proposal_requires_explicit_confirmation_for_exact_digest():
    docs = examples()
    draft = review_custom_format(
        "Practice", docs, (section(docs),), duration_minutes=60
    )
    assert draft == review_custom_format(
        "Practice",
        tuple(reversed(docs)),
        (section(tuple(reversed(docs))),),
        duration_minutes=60,
    )
    changed = review_custom_format(
        "Practice", docs, (section(docs),), duration_minutes=75
    )
    assert changed.digest != draft.digest
    with pytest.raises(ValueError, match="changed"):
        confirm_custom_format(changed, reviewed_digest=draft.digest)
    assert confirm_custom_format(draft, reviewed_digest=draft.digest).draft == draft


def test_each_section_must_cite_all_question_papers():
    docs = examples()
    with pytest.raises(ValueError, match="every question paper"):
        review_custom_format("Practice", docs, (section(docs[:2]),))


@pytest.mark.parametrize("page", [2, 3])
def test_citation_must_resolve_to_readable_page(page):
    docs = examples()
    with pytest.raises(ValueError, match="readable page"):
        review_custom_format(
            "Practice",
            docs,
            (
                section(
                    docs,
                    sources=[PageCitation(document_sha256=docs[0].sha256, page=page)],
                ),
            ),
        )


def test_missing_timing_is_not_invented_and_marks_are_derived():
    docs = examples()
    draft = review_custom_format(
        "Practice", docs, (section(docs), section(docs, id="b", candidate_marks=20))
    )
    assert draft.duration_minutes is None
    assert draft.candidate_marks == 60
    with pytest.raises(ValueError, match="identifiers"):
        review_custom_format("Practice", docs, (section(docs), section(docs)))


@pytest.mark.parametrize(
    "changes",
    [
        {"answer_count": 11},
        {"question_count": True},
        {"formats": ["written", "written"]},
    ],
)
def test_invalid_section_counts_and_formats(changes):
    with pytest.raises(ValueError):
        section(examples(), **changes)
