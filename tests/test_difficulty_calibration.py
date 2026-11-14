from __future__ import annotations

import json

import pytest

from tools import (
    aqa_accounting_calibration,
    aqa_business_calibration,
    difficulty_calibration,
    ocr_computer_science_calibration,
    ocr_economics_calibration,
)
from tools.coverage_matrix import GENERATOR_REGISTRY, RESOURCES, load_json

RETAINED_REPORTS = {
    "aqa/accounting": (aqa_accounting_calibration.OUTPUT, 12, "AQA-7127"),
    "aqa/business": (aqa_business_calibration.OUTPUT, 24, "AQA-7132"),
    "aqa/economics": (difficulty_calibration.OUTPUT, None, "Extract A:"),
    "ocr/computer-science": (
        ocr_computer_science_calibration.OUTPUT,
        8,
        "question-paper-",
    ),
    "ocr/economics": (ocr_economics_calibration.OUTPUT, 12, "question-paper-"),
}


def test_every_linked_calibration_has_an_explicit_evidence_contract() -> None:
    linked = [
        family["id"]
        for family in load_json(GENERATOR_REGISTRY)["families"]
        if "calibration_path" in family
    ]
    assert sorted(linked) == sorted(RETAINED_REPORTS)


@pytest.fixture(
    scope="module", params=tuple(RETAINED_REPORTS), ids=tuple(RETAINED_REPORTS)
)
def calibration(request):
    family_id = request.param
    output, document_count, forbidden_text = RETAINED_REPORTS[family_id]
    family = next(
        family
        for family in load_json(GENERATOR_REGISTRY)["families"]
        if family["id"] == family_id
    )
    assert RESOURCES / family["calibration_path"] == output
    return family, load_json(output), document_count, forbidden_text


def test_calibration_retains_no_official_text_or_paths(calibration) -> None:
    _, report, document_count, forbidden_text = calibration
    reference = report["reference"]
    if document_count is not None:
        assert reference["documents"] == document_count
    assert reference["derived_aggregate_only"] is True
    assert reference["retains_source_text"] is False
    rendered = json.dumps(report)
    assert "Reference Corpus" not in rendered
    assert forbidden_text not in rendered


def test_every_paper_has_multi_seed_structural_evidence(calibration) -> None:
    family, report, _, _ = calibration
    papers = report["generated"]["papers"]
    assert set(papers) == {paper["id"] for paper in family["papers"]}
    for paper in papers.values():
        assert paper["seeds"] == 20
        assert paper["unique_fingerprints"] == 20
        checks = paper["checks"]
        if family["id"] == "aqa/economics":
            for name in ("printed_mark_sequence", "page_count", "syllabus_coverage"):
                assert checks[name] is True
        else:
            assert paper["unique_stimulus_fingerprints"] == 20
            assert checks
            assert all(passed is True for passed in checks.values())


def test_difficulty_is_not_promoted_without_human_and_psychometric_evidence(
    calibration,
) -> None:
    family, report, _, _ = calibration
    gates = report["gates"]
    assert gates["automated_structural_demand"] is True
    assert gates["independent_subject_review"] is False
    assert gates["student_trial"] is False
    assert gates["psychometric_equivalence"] is False
    assert gates["difficulty_verified"] is False
    assert all(paper["checks"]["difficulty"] is False for paper in family["papers"])
