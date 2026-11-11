"""Originality evidence must not expose mutable screening policy."""

import json
from difflib import SequenceMatcher
from itertools import product

import pytest

from Backend.Core.france import originality


@pytest.fixture
def policy(monkeypatch):
    # Isolate the genuine red mutation from other tests in this interpreter.
    baseline = dict(originality.THRESHOLDS)
    monkeypatch.setattr(originality, "THRESHOLDS", dict(baseline))
    return baseline


def candidate():
    return (
        "Un observatoire étudie les déplacements de tortues marines. "
        "Construire le graphe des stations et justifier un itinéraire minimal."
    )


def test_reports_have_independent_policy_snapshots(policy):
    first = originality.screen_originality(candidate(), [])
    second = originality.screen_originality(candidate(), [])
    assert first["thresholds"] is not originality.THRESHOLDS
    assert first["thresholds"] is not second["thresholds"]
    first["thresholds"]["contiguous_characters"] = 1_000_000
    assert second["thresholds"] == policy
    assert policy == originality.THRESHOLDS


def test_mutating_a_report_cannot_disable_later_copy_refusal(policy):
    report = originality.screen_originality(candidate(), [])
    for name in report["thresholds"]:
        report["thresholds"][name] = 1_000_000
    with pytest.raises(originality.SimilarityRejected, match="originalité"):
        originality.screen_originality(candidate(), [candidate()])
    assert policy == originality.THRESHOLDS


def test_scoped_copy_check_allows_shared_terms_and_rejects_a_long_block():
    excerpt = " ".join(f"élément{index}" for index in range(40))
    originality.reject_contiguous_reference_copy(
        ["Les éléments sont rangés dans un dictionnaire.", excerpt[:50]], [excerpt]
    )
    with pytest.raises(originality.SimilarityRejected, match="extrait officiel"):
        originality.reject_contiguous_reference_copy(
            ["Les éléments suivants sont étudiés.", excerpt.upper()], [excerpt]
        )


def test_serialized_report_keeps_existing_policy_and_counts(policy):
    report = originality.screen_originality(candidate(), [])
    saved = json.loads(json.dumps(report))
    assert saved["state"] == "passed_calibrated_screen"
    assert saved["calibration_set"] == "fr-nsi-labelled-v1"
    assert saved["thresholds"] == policy
    assert saved["maximum_scores"] == {name: 0 for name in policy}
    assert saved["comparison_counts"] == {"references": 0, "previous_generations": 0}
    assert saved["copyright_guarantee"] is False
    assert saved["teacher_review_required"] is True


def test_contiguous_match_keeps_exact_scores_including_unicode_and_empty_inputs():
    texts = [
        "".join(chars) for length in range(5) for chars in product("aé ", repeat=length)
    ]
    for left, right in product(texts, repeat=2):
        old = SequenceMatcher(None, left, right, autojunk=False).find_longest_match()
        assert originality._longest_common_substring(left, right) == old.size


def test_originality_uses_bounded_contiguous_index_not_character_sequence_matcher(
    monkeypatch,
):
    matcher = originality.SequenceMatcher

    def token_matcher(junk, left, right, *, autojunk):
        assert not isinstance(left, str)
        assert not isinstance(right, str)
        return matcher(junk, left, right, autojunk=autojunk)

    monkeypatch.setattr(originality, "SequenceMatcher", token_matcher)
    shared = "éà" * 800
    assert originality._scores("début " + shared, shared + " fin")[
        "contiguous_characters"
    ] == len(shared)
