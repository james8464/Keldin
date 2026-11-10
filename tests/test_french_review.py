import json
from hashlib import sha256

import pytest


@pytest.mark.parametrize("reviewer", ["Professeur test", "  Professeur test  "])
def test_review_is_bound_to_all_artifacts_and_becomes_stale(tmp_path, reviewer):
    from Backend.Core.france.teacher_review import record_review, review_status

    document = tmp_path / "sujet.pdf"
    document.write_bytes(b"example test artifact")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "artifacts": {
                    "question_paper": {
                        "file": "sujet.pdf",
                        "sha256": sha256(document.read_bytes()).hexdigest(),
                    }
                }
            }
        )
    )
    record = record_review(
        manifest,
        reviewer=reviewer,
        decision="revise",
        scores={
            key: 3
            for key in (
                "correctness",
                "curriculum",
                "language",
                "difficulty",
                "timing",
                "marking",
                "layout",
                "originality",
            )
        },
        notes="Corriger le premier exercice.",
    )
    assert review_status(manifest, record) == "revise"
    document.write_bytes(b"edited artifact")
    assert review_status(manifest, record) == "stale"


def test_review_rejects_unsafe_manifest_and_incomplete_rubric(tmp_path):
    from Backend.Core.france.teacher_review import record_review

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "artifacts": {
                    "question_paper": {"file": "../outside.pdf", "sha256": "0" * 64}
                }
            }
        )
    )
    with pytest.raises(ValueError):
        record_review(manifest, reviewer="", decision="approved", scores={}, notes="")


def test_review_cli_writes_an_immutable_hash_bound_record(tmp_path):
    from argparse import Namespace

    from Backend.Core.france.teacher_review import handle_record_review, review_status

    document = tmp_path / "sujet.pdf"
    document.write_bytes(b"paper")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "artifacts": {
                    "question_paper": {
                        "file": document.name,
                        "sha256": sha256(document.read_bytes()).hexdigest(),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    args = Namespace(
        manifest=manifest,
        reviewer="Mme Martin",
        decision="revise",
        scores_json=json.dumps(
            {
                key: 3
                for key in (
                    "correctness",
                    "curriculum",
                    "language",
                    "difficulty",
                    "timing",
                    "marking",
                    "layout",
                    "originality",
                )
            }
        ),
        notes="Revoir la formulation de la question 2.",
    )
    assert handle_record_review(args) == 0
    records = list(tmp_path.glob("teacher-review-*.json"))
    assert len(records) == 1
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert review_status(manifest, record) == "revise"


def test_cli_exposes_french_teacher_review_without_changing_legacy_generation():
    from Backend.Core.cli import build_parser

    args = build_parser().parse_args(
        [
            "review-french-assessment",
            "--manifest",
            "/tmp/manifest.json",
            "--reviewer",
            "Mme Martin",
            "--decision",
            "revise",
            "--scores-json",
            "{}",
            "--notes",
            "À revoir",
        ]
    )
    assert args.manifest.name == "manifest.json"
    assert args.decision == "revise"


@pytest.fixture
def synthetic_review(tmp_path):
    from Backend.Core.france.teacher_review import RUBRIC, record_review

    artifact = tmp_path / "synthetic.bin"
    artifact.write_bytes(b"Synthetic fixture only; not a paper or human evidence")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "artifacts": {
                    "fixture": {
                        "file": artifact.name,
                        "sha256": sha256(artifact.read_bytes()).hexdigest(),
                    }
                }
            }
        )
    )
    record = record_review(
        manifest,
        reviewer="SYNTHETIC TEST ONLY",
        decision="revise",
        scores={key: 3 for key in RUBRIC},
        notes="Synthetic fixture, no real review.",
    )
    return manifest, record


def test_repeat_review_with_new_timestamp_retains_original_record(synthetic_review):
    from Backend.Core.france.teacher_review import _write_record, record_review

    manifest, first = synthetic_review
    first["created_at"] = "2000-01-01T00:00:00+00:00"
    destination = _write_record(manifest, first)
    original = destination.read_bytes()
    repeated = record_review(
        manifest,
        reviewer=first["reviewer"],
        decision=first["decision"],
        scores=first["scores"],
        notes=first["notes"],
    )
    assert repeated["record_id"] == first["record_id"]
    assert repeated["created_at"] != first["created_at"]
    assert _write_record(manifest, repeated) == destination
    assert destination.read_bytes() == original
    assert len(list(manifest.parent.glob("teacher-review-*.json"))) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "identity",
        "reviewer",
        "decision",
        "scores",
        "notes",
        "credentials",
        "schema",
        "schema-bool",
        "score-float",
        "missing-time",
        "extra",
    ],
)
def test_repeat_review_refuses_every_other_existing_record_difference(
    synthetic_review, mutation
):
    from copy import deepcopy

    from Backend.Core.france.teacher_review import _write_record

    manifest, record = synthetic_review
    destination = _write_record(manifest, record)
    changed = deepcopy(record)
    if mutation == "identity":
        changed["identity"]["manifest_sha256"] = "0" * 64
    elif mutation == "scores":
        changed["scores"]["layout"] = 2
    elif mutation == "score-float":
        changed["scores"]["layout"] = 3.0
    elif mutation == "missing-time":
        changed.pop("created_at")
    elif mutation == "extra":
        changed["unexpected"] = "refuse"
    else:
        key, value = {
            "reviewer": ("reviewer", "OTHER SYNTHETIC FIXTURE"),
            "decision": ("decision", "rejected"),
            "notes": ("notes", "Changed synthetic notes"),
            "credentials": ("credential_status", "forged"),
            "schema": ("schema_version", 2),
            "schema-bool": ("schema_version", True),
        }[mutation]
        changed[key] = value
    destination.write_text(json.dumps(changed))
    before = destination.read_bytes()
    with pytest.raises(ValueError):
        _write_record(manifest, dict(record, created_at="2000-01-03T00:00:00+00:00"))
    assert destination.read_bytes() == before


@pytest.mark.parametrize("dangling", [False, True])
def test_repeat_review_refuses_symlink_without_touching_target(
    synthetic_review, dangling
):
    from Backend.Core.france.teacher_review import _write_record

    manifest, record = synthetic_review
    target = manifest.parent / "owned-target.json"
    if not dangling:
        target.write_text(json.dumps(record))
    destination = manifest.parent / f"teacher-review-{record['record_id'][:12]}.json"
    destination.symlink_to(target)
    before = target.read_bytes() if not dangling else None
    with pytest.raises(ValueError):
        _write_record(manifest, record)
    assert (target.read_bytes() if target.exists() else None) == before
    assert destination.is_symlink()


@pytest.mark.parametrize("serialized", ["not JSON", "[]"])
def test_repeat_review_refuses_malformed_or_nonobject_record(
    synthetic_review, serialized
):
    from Backend.Core.france.teacher_review import _write_record

    manifest, record = synthetic_review
    destination = _write_record(manifest, record)
    destination.write_text(serialized)
    before = destination.read_bytes()
    with pytest.raises(ValueError):
        _write_record(manifest, record)
    assert destination.read_bytes() == before


def test_repeat_review_accepts_benign_formatting_without_rewriting(synthetic_review):
    from Backend.Core.france.teacher_review import _write_record

    manifest, record = synthetic_review
    destination = _write_record(manifest, record)
    reordered = dict(reversed(list(record.items())))
    destination.write_text(json.dumps(reordered, ensure_ascii=True, indent=4))
    before = destination.read_bytes()
    assert (
        _write_record(manifest, dict(record, created_at="2000-01-03T00:00:00+00:00"))
        == destination
    )
    assert destination.read_bytes() == before
