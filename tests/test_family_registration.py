"""Exercise a new practice family through the real registry and CLI."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from Backend.Core import generation, generator_registry, reference_demand
from Backend.Core.cli import main
from Backend.Core.paths import REPO_ROOT
from tools.live_generation_matrix import matrix_jobs


@pytest.fixture
def experimental_family(tmp_path, monkeypatch):
    """Stage synthetic config only; use the real shared generator and validators."""
    fixture_root = tmp_path / "project"
    resources = fixture_root / "Resources"
    resources.mkdir(parents=True)
    source = REPO_ROOT / "Resources"
    (resources / "configured-generators").symlink_to(source / "configured-generators")
    shutil.copy2(source / "layout-master-runtime.json", resources)

    registry_path = resources / "generator-registry.json"
    registry = json.loads(generator_registry.REGISTRY_PATH.read_text(encoding="utf-8"))
    prototype = next(
        family for family in registry["families"] if family["id"] == "aqa/mathematics"
    )
    family_id = "aqa/example-calculation"
    subject = "example_calculation"
    paper = "core"
    syllabus_path = resources / "example-family.json"
    syllabus = json.loads(
        (source / prototype["syllabus_path"]).read_text(encoding="utf-8")
    )
    syllabus.update(
        family_id=family_id,
        backend_subject=subject,
        subject_label="Example calculation",
    )
    syllabus["papers"] = [
        syllabus["papers"][0]
        | {"id": paper, "code": "Example", "title": "Example calculation"}
    ]
    syllabus["topics"] = [
        topic | {"papers": [paper]}
        for topic in syllabus["topics"]
        if "1" in topic["papers"]
    ]
    syllabus_path.write_text(json.dumps(syllabus), encoding="utf-8")

    configured = prototype | {
        "id": family_id,
        "app_subject": subject,
        "backend_subject": subject,
        "subject": "example-calculation",
        "resource_path": "configured-generators",
        "syllabus_path": syllabus_path.name,
        "declared_papers": [paper],
        "advertised": True,
        "outputs_by_paper": {paper: prototype["outputs_by_paper"]["1"]},
        "papers": [prototype["papers"][0] | {"id": paper}],
    }
    candidate_registry = registry | {"families": [configured]}
    registry_path.write_text(json.dumps(candidate_registry), encoding="utf-8")
    profiles_path = resources / "reference-demand-profiles.json"
    profiles = json.loads(reference_demand.PROFILES_PATH.read_text(encoding="utf-8"))
    profile = next(
        p
        for p in profiles["profiles"]
        if (p["family_id"], p["paper_id"]) == ("aqa/mathematics", "1")
    )
    profiles_path.write_text(
        json.dumps(
            profiles
            | {"profiles": [profile | {"family_id": family_id, "paper_id": paper}]}
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(generator_registry, "REGISTRY_PATH", registry_path)
    monkeypatch.setattr(generation, "REPO_ROOT", fixture_root)
    monkeypatch.setattr(reference_demand, "PROFILES_PATH", profiles_path)
    load_profiles = reference_demand.load_reference_demand_document
    monkeypatch.setattr(
        reference_demand,
        "load_reference_demand_document",
        lambda: load_profiles(profiles_path),
    )
    monkeypatch.setattr(generation, "hosted_client", _offline_client)
    generator_registry.generator_capabilities.cache_clear()
    try:
        yield subject, paper, syllabus, candidate_registry
    finally:
        generator_registry.generator_capabilities.cache_clear()
        load_profiles.cache_clear()


def _offline_client(*, dry_run, **_kwargs):
    assert dry_run, "the registration fixture must never call a hosted model"
    return None


def test_data_only_family_runs_through_publication(
    experimental_family, tmp_path, capsys, monkeypatch
):
    subject, paper, syllabus, registry = experimental_family
    assert [job.id for job in matrix_jobs(registry)] == [f"{subject}:{paper}"]
    assert generator_registry.generator_capability(subject).entry_point_contract == (
        "request-v1"
    )

    def accidental_legacy_dispatch(*_args, **_kwargs):
        pytest.fail("the configured family must not use legacy signature inspection")

    monkeypatch.setattr(
        "Backend.Core.generator_entry_points._legacy_arguments",
        accidental_legacy_dispatch,
    )
    output = tmp_path / "export"
    assert (
        main(
            [
                "generate",
                "--dry-run",
                "--subject",
                subject,
                "--paper",
                paper,
                "--output",
                str(output),
                "--seed",
                "1234",
            ]
        )
        == 0
    )
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[-1]["type"] == "done"
    files = {e["role"]: Path(e["path"]) for e in events if e["type"] == "file"}
    assert set(files) == {
        "question_paper",
        "mark_scheme",
        "assessment_package",
        "package_manifest",
    }
    assert all(path.parent == output and path.is_file() for path in files.values())
    package = json.loads(files["assessment_package"].read_text(encoding="utf-8"))
    assert package["subject"] == subject and package["paper"] == paper
    assert (
        sum(item["marks"] for item in package["items"])
        == syllabus["papers"][0]["marks"]
    )
    manifest = json.loads(files["package_manifest"].read_text(encoding="utf-8"))
    assert manifest["request"]["preview_mode"] is True
    assert (
        manifest["evidence"]["assessment_validation"]["fingerprints_verified"] is True
    )
    for role, evidence in manifest["outputs"].items():
        assert (
            evidence["sha256"] == hashlib.sha256(files[role].read_bytes()).hexdigest()
        )
    assert (
        manifest["evidence"]["qualification_levels"]["empirically_calibrated"] is False
    )
