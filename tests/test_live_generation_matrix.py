from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.live_generation_matrix import (
    REGISTRY_PATH,
    _request_identity,
    _resumable_result,
    _sha256,
    main,
    matrix_jobs,
    matrix_markdown,
    run_matrix,
)
from tools.live_process import BackendRun


@pytest.mark.parametrize(
    "terminal_events, expected",
    [
        ([{"type": "done"}], True),
        ([{"type": "progress"}, {"type": "done"}], True),
        ([{"type": "error", "message": "failed"}, {"type": "done"}], False),
        ([{"type": "done"}, {"type": "error", "message": "failed"}], False),
        ([{"type": "done"}, {"type": "progress"}], False),
        ([{"type": "done"}, {"type": "done"}], False),
        ([], False),
    ],
)
def test_matrix_requires_an_error_free_terminal_event_stream(
    tmp_path, monkeypatch, terminal_events, expected
):
    job = jobs()[0]

    def complete(command, **_kwargs):
        run_dir = Path(command[command.index("--output") + 1])
        files = published_files(run_dir, job)
        events = [
            {"type": "file", "role": role, "path": path} for role, path in files.items()
        ]
        return BackendRun(
            0, False, "\n".join(map(json.dumps, events + terminal_events)), "", 1000
        )

    monkeypatch.setattr("tools.live_generation_matrix.run_backend", complete)
    report = run_matrix(
        [job],
        output_root=tmp_path,
        command_prefix=["backend"],
        model="gemma4:12b",
        provider="ollama",
        ollama_url="http://localhost:11434",
        base_seed=42,
        timeout_seconds=30,
        dry_run=False,
        resume=False,
    )
    result = report["results"][0]
    assert result["passed"] is expected
    assert result["generation_passed"] is expected
    manifest = json.loads(Path(result["qualification_manifest"]).read_text())
    assert manifest["gate_results"]["generation"] == (
        "passed" if expected else "failed"
    )
    if not expected:
        assert result["errors"]

    # Old writers may have saved the contradictory stream as passing. Hashes alone
    # must not let that retained result bypass the current protocol checks.
    result["passed"] = True
    result["generation_passed"] = True
    result["errors"] = []
    path = tmp_path / job.backend_subject / f"paper-{job.paper}" / "matrix-result.json"
    path.write_text(json.dumps(result))
    resumed = _resumable_result(path, request_identity=result["request_identity"])
    assert (resumed is not None) is expected


@pytest.fixture(autouse=True)
def model_identity(monkeypatch):
    monkeypatch.setattr(
        "tools.live_generation_matrix._model_digest", lambda *args: "model-digest"
    )


def request_identity(job, *, seed=42, model="gemma4:12b", preview=False):
    return _request_identity(
        job,
        seed=seed,
        model=model,
        provider="ollama",
        ollama_url="http://localhost:11434",
        dry_run=preview,
        command_prefix=["backend"],
        model_digest=None if preview else "model-digest",
    )


def jobs():
    return matrix_jobs(json.loads(REGISTRY_PATH.read_text(encoding="utf-8")))


def file_event_stream(files: dict[str, str]) -> str:
    events = [
        {"type": "file", "role": role, "path": path} for role, path in files.items()
    ]
    return "\n".join(map(json.dumps, [*events, {"type": "done"}])) + "\n"


def published_files(
    run_dir,
    job,
    *,
    seed=42,
    model="gemma4:12b",
    provider="ollama",
    preview=False,
    demand=True,
    extra=None,
):
    import pymupdf

    files = {}
    outputs = {}
    for role in job.expected_roles:
        if role == "assessment_package":
            path = run_dir / f"{role}.json"
            payload = (
                {}
                if demand is None
                else {
                    "reference_demand": {
                        "passed": demand,
                        "failed_checks": []
                        if demand
                        else ["mark_weighted_demand_distribution"],
                    }
                }
            )
            path.write_text(json.dumps(payload), encoding="utf-8")
            pdf_validation = None
        else:
            path = run_dir / f"{role}.pdf"
            with pymupdf.open() as doc:
                doc.new_page().insert_text((70, 70), f"Practice {role}")
                doc.save(path)
            pdf_validation = {"pages": 1}
        files[role] = str(path)
        outputs[role] = dict(
            filename=path.name,
            bytes=path.stat().st_size,
            sha256=_sha256(path),
            pdf_validation=pdf_validation,
        )
    manifest = run_dir / "package.json"
    payload = {
        "schema_version": 2,
        "generator": {"id": job.family_id, "version": "1.2.3"},
        "request": {
            "subject": job.backend_subject,
            "paper": job.paper,
            "seed": seed,
            "preview_mode": preview,
            "model": model,
            "provider": provider,
        },
        "outputs": outputs,
    }
    payload.update(extra or {})
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    files["package_manifest"] = str(manifest)
    return files


@pytest.mark.parametrize("defect", ["none", "seed", "preview", "digest", "not_pdf"])
def test_matrix_qualifies_only_the_bound_published_pdfs(tmp_path, monkeypatch, defect):
    job = jobs()[0]

    def backend(_command, *, run_dir, **_kwargs):
        files = published_files(run_dir, job)
        manifest = Path(files["package_manifest"])
        packet = json.loads(manifest.read_text())
        paper = Path(files["question_paper"])
        if defect == "seed":
            packet["request"]["seed"] = 43
        elif defect == "preview":
            packet["request"]["preview_mode"] = True
        elif defect == "digest":
            packet["outputs"]["question_paper"]["sha256"] = "0" * 64
        elif defect == "not_pdf":
            paper.write_text("Not a document.")
            packet["outputs"]["question_paper"].update(
                bytes=paper.stat().st_size, sha256=_sha256(paper)
            )
        manifest.write_text(json.dumps(packet), encoding="utf-8")
        return BackendRun(0, False, file_event_stream(files), "", 1000)

    monkeypatch.setattr("tools.live_generation_matrix.run_backend", backend)
    report = run_matrix(
        [job],
        output_root=tmp_path,
        command_prefix=["backend"],
        model="gemma4:12b",
        provider="ollama",
        ollama_url="http://localhost:11434",
        base_seed=42,
        timeout_seconds=30,
        dry_run=False,
        resume=False,
    )
    result = report["results"][0]
    assert result["passed"] == (defect == "none")
    qualification = json.loads(Path(result["qualification_manifest"]).read_text())
    assert qualification["gate_results"]["pdf"] == (
        "passed" if defect == "none" else "failed"
    )
    # A retained result with the same file hashes still cannot promote a
    # mismatched publication manifest simply by calling itself passed.
    result.update(passed=True, generation_passed=True, errors=[])
    retained = Path(result["qualification_manifest"]).with_name("matrix-result.json")
    retained.write_text(json.dumps(result), encoding="utf-8")
    assert (
        _resumable_result(retained, request_identity=result["request_identity"])
        is not None
    ) is (defect == "none")


@pytest.mark.parametrize(
    "wrong_evidence",
    ["duplicate_role", "outside_job", "shared_file", "external_symlink"],
)
def test_matrix_refuses_file_events_not_owned_by_this_job(
    tmp_path, monkeypatch, wrong_evidence
):
    job = jobs()[0]

    def complete(command, *, run_dir, **_kwargs):
        files = {}
        for role in (*job.expected_roles, "package_manifest"):
            path = run_dir / f"{role}.json"
            path.write_text(json.dumps({"reference_demand": {"passed": True}}))
            files[role] = str(path)
        if wrong_evidence == "duplicate_role":
            events = file_event_stream(files)
            return BackendRun(
                0, False, events.splitlines()[0] + "\n" + events, "", 1000
            )
        if wrong_evidence in {"outside_job", "external_symlink"}:
            other_paper = tmp_path / "past-paper.json"
            other_paper.write_text("{}", encoding="utf-8")
            if wrong_evidence == "external_symlink":
                alias = run_dir / "paper-alias.json"
                alias.symlink_to(other_paper)
                files["question_paper"] = str(alias)
            else:
                files["question_paper"] = str(other_paper)
        else:
            files["question_paper"] = files["mark_scheme"]
        return BackendRun(0, False, file_event_stream(files), "", 1000)

    monkeypatch.setattr("tools.live_generation_matrix.run_backend", complete)
    report = run_matrix(
        [job],
        output_root=tmp_path,
        command_prefix=["backend"],
        model="gemma4:12b",
        provider="ollama",
        ollama_url="http://localhost:11434",
        base_seed=42,
        timeout_seconds=30,
        dry_run=False,
        resume=False,
    )
    (result,) = report["results"]
    assert not result["generation_passed"]
    assert not result["passed"]
    assert result["errors"]


def test_live_matrix_is_derived_from_every_advertised_registry_paper() -> None:
    value = jobs()

    assert len(value) == 21
    assert [job.seed_offset for job in value] == list(range(21))
    assert len({job.id for job in value}) == 21
    assert {job.backend_subject for job in value} == {
        "accounting_aqa",
        "business_aqa",
        "computer_science",
        "computer_science_ocr",
        "economics",
        "economics_aqa",
        "economics_ocr",
    }
    assert all("assessment_package" in job.expected_roles for job in value)


def test_apple_system_matrix_uses_packaged_backend_and_system_model(
    tmp_path, monkeypatch
):
    captured = {}

    def capture(jobs, **kwargs):
        captured.update(kwargs)
        assert len(jobs) == 21
        return {"summary": {"failed": 0}}

    monkeypatch.setattr("tools.live_generation_matrix.run_matrix", capture)
    executable = apple_system_fixture(tmp_path)
    assert (
        main(
            [
                "--output",
                str(tmp_path / "results"),
                "--provider",
                "apple_intelligence",
                "--backend-executable",
                str(executable),
            ]
        )
        == 0
    )
    assert captured["provider"] == "apple_intelligence"
    assert captured["model"] == "apple-system-on-device"
    assert captured["command_prefix"] == [str(executable.resolve())]
    assert not captured["resume"]


def apple_system_fixture(root):
    contents = root / "Keldin.app" / "Contents"
    backend = contents / "Resources" / "KeldinBackend" / "KeldinBackend"
    helper = contents / "Helpers" / "KeldinAppleIntelligence"
    for executable in (backend, helper):
        executable.parent.mkdir(parents=True)
        executable.touch()
        executable.chmod(0o700)
    return backend


def test_apple_system_identity_changes_when_bundled_helper_changes(tmp_path):
    backend = apple_system_fixture(tmp_path)
    helper = backend.parents[2] / "Helpers" / "KeldinAppleIntelligence"

    def identity():
        return _request_identity(
            jobs()[0],
            seed=42,
            model="apple-system-on-device",
            provider="apple_intelligence",
            ollama_url="http://localhost:11434",
            dry_run=False,
            command_prefix=[str(backend)],
            model_digest=None,
            runtime_sha256="source-fixture",
        )

    before = identity()
    assert before["apple_system_helper_sha256"] == _sha256(helper)
    assert before["model_digest"] is None
    helper.write_bytes(b"changed helper")
    assert identity() != before


@pytest.mark.parametrize(
    "reason", ["no_backend", "not_packaged", "no_helper", "wrong_model", "resume"]
)
def test_apple_system_matrix_rejects_invalid_requests_before_launch(
    tmp_path, monkeypatch, reason
):
    backend = apple_system_fixture(tmp_path)
    args = ["--output", str(tmp_path / "results"), "--provider", "apple_intelligence"]
    if reason == "not_packaged":
        backend = tmp_path / "KeldinBackend"
        backend.touch()
        backend.chmod(0o700)
    if reason != "no_backend":
        args.extend(["--backend-executable", str(backend)])
    if reason == "no_helper":
        (backend.parents[2] / "Helpers" / "KeldinAppleIntelligence").unlink()
    if reason == "wrong_model":
        args.extend(["--model", "different-model"])
    if reason == "resume":
        args.append("--resume")
    monkeypatch.setattr(
        "tools.live_generation_matrix.run_matrix",
        lambda *a, **kw: pytest.fail("must not launch"),
    )
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    assert not (tmp_path / "results").exists()


def test_live_matrix_markdown_reports_failures_without_false_success() -> None:
    report = {
        "model": "test:model",
        "summary": {"papers": 1, "passed": 0, "failed": 1},
        "results": [
            {
                "family_id": "test/family",
                "paper": "1",
                "passed": False,
                "duration_seconds": 12.2,
                "errors": ["model rejected the schema"],
            }
        ],
    }

    rendered = matrix_markdown(report)
    assert "0/1 papers passed" in rendered
    assert "model rejected the schema" in rendered


def test_live_matrix_reports_backend_signal_exit_without_event_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    job = jobs()[0]

    def trapped(command, **_kwargs):
        return BackendRun(-5, False, "", "", 1000)

    monkeypatch.setattr("tools.live_generation_matrix.run_backend", trapped)

    report = run_matrix(
        [job],
        output_root=tmp_path,
        command_prefix=["backend"],
        model="gemma4:12b",
        provider="ollama",
        ollama_url="http://localhost:11434",
        base_seed=42,
        timeout_seconds=30,
        dry_run=False,
        resume=False,
    )

    errors = report["results"][0]["errors"]
    assert errors == ["backend terminated by signal SIGTRAP (5)"]
    assert "SIGTRAP" in (tmp_path / "matrix-report.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("demand_passed", [True, False, None])
def test_live_matrix_writes_per_paper_and_aggregate_qualification_manifests(
    tmp_path: Path,
    monkeypatch,
    demand_passed,
) -> None:
    job = jobs()[0]

    def complete(command, **_kwargs):
        run_dir = Path(command[command.index("--output") + 1])
        files = published_files(
            run_dir,
            job,
            demand=demand_passed,
            extra={
                "inputs": {
                    "assessment_schema": "assessment:v3",
                    "assessment_package_schema": 1,
                    "syllabus_sha256": "b" * 64,
                    "layout_profile_sha256": "c" * 64,
                }
            },
        )
        return BackendRun(0, False, file_event_stream(files), "", 1000)

    monkeypatch.setattr("tools.live_generation_matrix.run_backend", complete)

    report = run_matrix(
        [job],
        output_root=tmp_path,
        command_prefix=["backend"],
        model="gemma4:12b",
        provider="ollama",
        ollama_url="http://localhost:11434",
        base_seed=42,
        timeout_seconds=30,
        dry_run=False,
        resume=False,
    )

    result = report["results"][0]
    manifest_path = Path(result["qualification_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    aggregate = json.loads(
        (tmp_path / "qualification-run-manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["generator_id"] == job.family_id
    assert manifest["paper_id"] == job.paper
    assert manifest["seed"] == 42
    assert manifest["model"]["name"] == "gemma4:12b"
    assert manifest["gate_results"]["generation"] == "passed"
    assert manifest["gate_results"]["reference_demand"] == (
        "passed" if demand_passed else "failed"
    )
    assert manifest["gate_results"]["visual"] == "not_run"
    assert {artifact["role"] for artifact in manifest["artifacts"]} == (
        set(job.expected_roles) | {"package_manifest"}
    )
    assert aggregate["paper_manifests"][0]["sha256"]
    assert aggregate["summary"] == {
        "papers": 1,
        "passed": int(bool(demand_passed)),
        "failed": int(not demand_passed),
    }
    if not demand_passed:
        assert result["errors"]


def test_resume_backfills_qualification_evidence_without_regenerating(
    tmp_path: Path,
    monkeypatch,
) -> None:
    job = jobs()[0]
    run_dir = tmp_path / job.backend_subject / f"paper-{job.paper}"
    run_dir.mkdir(parents=True)
    files = published_files(run_dir, job, seed=99)
    (run_dir / "events.jsonl").write_text(file_event_stream(files), encoding="utf-8")
    previous = {
        "id": job.id,
        "family_id": job.family_id,
        "backend_subject": job.backend_subject,
        "paper": job.paper,
        "title": job.title,
        "detail": job.detail,
        "seed": 99,
        "model": "gemma4:12b",
        "provider": "ollama",
        "preview": False,
        "duration_seconds": 10,
        "return_code": 0,
        "timed_out": False,
        "passed": True,
        "missing_roles": [],
        "missing_files": [],
        "errors": [],
        "files": files,
        "request_identity": request_identity(job, seed=99),
        "artifact_sha256": {role: _sha256(Path(path)) for role, path in files.items()},
        "events_sha256": _sha256(run_dir / "events.jsonl"),
    }
    result_path = run_dir / "matrix-result.json"
    result_path.write_text(json.dumps(previous), encoding="utf-8")

    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("resume regenerated an already passing paper")

    monkeypatch.setattr("tools.live_generation_matrix.run_backend", unexpected_call)

    report = run_matrix(
        [job],
        output_root=tmp_path,
        command_prefix=["backend"],
        model="gemma4:12b",
        provider="ollama",
        ollama_url="http://localhost:11434",
        base_seed=99,
        timeout_seconds=30,
        dry_run=False,
        resume=True,
    )

    manifest = Path(report["results"][0]["qualification_manifest"])
    assert manifest.is_file()
    assert (tmp_path / "qualification-run-manifest.json").is_file()
    substituted = run_dir / "substituted.json"
    substituted.write_text("{}", encoding="utf-8")
    previous["files"]["question_paper"] = str(substituted)
    previous["artifact_sha256"]["question_paper"] = _sha256(substituted)
    result_path.write_text(json.dumps(previous), encoding="utf-8")
    assert (
        _resumable_result(result_path, request_identity=previous["request_identity"])
        is None
    )


@pytest.mark.parametrize(
    "change", ["none", "wrong_artifact", "manual_gate", "outside", "symlink"]
)
def test_resume_only_aggregates_current_automation_evidence(
    tmp_path, monkeypatch, change
):
    job = jobs()[0]
    output = tmp_path / "run"

    def backend(command, **_kwargs):
        run_dir = Path(command[command.index("--output") + 1])
        files = published_files(run_dir, job)
        return BackendRun(0, False, file_event_stream(files), "", 1000)

    monkeypatch.setattr("tools.live_generation_matrix.run_backend", backend)
    arguments = dict(
        output_root=output,
        command_prefix=["backend"],
        model="gemma4:12b",
        provider="ollama",
        ollama_url="http://localhost:11434",
        base_seed=42,
        timeout_seconds=30,
        dry_run=False,
    )
    first = run_matrix([job], resume=False, **arguments)["results"][0]
    assert first["passed"]
    manifest = Path(first["qualification_manifest"])
    original = manifest.read_bytes()
    payload = json.loads(original)
    if change == "wrong_artifact":
        payload["artifacts"][0]["sha256"] = "0" * 64
        manifest.write_text(json.dumps(payload))
    elif change == "manual_gate":
        payload["gate_results"]["visual"] = "passed"
        manifest.write_text(json.dumps(payload))
    elif change in {"outside", "symlink"}:
        unrelated = tmp_path / "unrelated.json"
        unrelated.write_bytes(original)
        if change == "outside":
            result_path = manifest.with_name("matrix-result.json")
            result = json.loads(result_path.read_bytes())
            result["qualification_manifest"] = str(unrelated)
            result_path.write_text(json.dumps(result))
        else:
            manifest.unlink()
            manifest.symlink_to(unrelated)
    old_evidence = manifest.read_bytes()

    def no_inference(*_args, **_kwargs):
        pytest.fail("verified paper should not regenerate because of stale evidence")

    monkeypatch.setattr("tools.live_generation_matrix.run_backend", no_inference)
    resumed = run_matrix([job], resume=True, **arguments)["results"][0]
    assert resumed["passed"]
    used = Path(resumed["qualification_manifest"])
    assert used.is_relative_to(manifest.parent)
    current = json.loads(used.read_bytes())
    original_payload = json.loads(original)
    assert current["artifacts"] == original_payload["artifacts"]
    assert current["gate_results"] == original_payload["gate_results"]
    assert current["evidence"] == original_payload["evidence"]
    aggregate = json.loads((output / "qualification-run-manifest.json").read_bytes())
    record = aggregate["paper_manifests"][0]
    assert output / record["path"] == used
    assert record["sha256"] == _sha256(used)
    if change in {"wrong_artifact", "manual_gate"}:
        assert any(
            path.read_bytes() == old_evidence
            for path in manifest.parent.glob("qualification-manifest*.json")
        ), "external review or stale evidence should remain recoverable"
    elif change in {"none", "outside"}:
        assert used.read_bytes() == original
    if change in {"outside", "symlink"}:
        assert unrelated.read_bytes() == original
    if change == "symlink":
        assert manifest.is_symlink() and used != manifest


def test_final_aggregate_does_not_reissue_an_edited_earlier_review(
    tmp_path, monkeypatch
):
    selected = jobs()[:2]
    earliest = (
        tmp_path
        / selected[0].backend_subject
        / f"paper-{selected[0].paper}"
        / "qualification-manifest.json"
    )

    def backend(command, **_kwargs):
        run_dir = Path(command[command.index("--output") + 1])
        job = next(job for job in selected if run_dir.name == f"paper-{job.paper}")
        if job is selected[1]:
            payload = json.loads(earliest.read_bytes())
            payload["gate_results"]["visual"] = "passed"
            earliest.write_text(json.dumps(payload))
        files = published_files(run_dir, job, seed=42 + job.seed_offset)
        return BackendRun(0, False, file_event_stream(files), "", 1000)

    monkeypatch.setattr("tools.live_generation_matrix.run_backend", backend)
    report = run_matrix(
        selected,
        output_root=tmp_path,
        command_prefix=["backend"],
        model="gemma4:12b",
        provider="ollama",
        ollama_url="http://localhost:11434",
        base_seed=42,
        timeout_seconds=30,
        dry_run=False,
        resume=False,
    )
    assert report["summary"]["passed"] == 2
    fresh = Path(report["results"][0]["qualification_manifest"])
    assert fresh.parent == earliest.parent and fresh != earliest
    assert json.loads(fresh.read_bytes())["gate_results"]["visual"] == "not_run"
    assert json.loads(earliest.read_bytes())["gate_results"]["visual"] == "passed"


@pytest.mark.parametrize(
    "changed", ["model", "seed", "preview", "runtime", "artifact", "role", "events"]
)
def test_resume_never_reuses_a_different_generation_request(
    tmp_path, monkeypatch, changed
):
    job = jobs()[0]
    run_dir = tmp_path / job.backend_subject / f"paper-{job.paper}"
    run_dir.mkdir(parents=True)
    files = {}
    for role in (*job.expected_roles, "package_manifest"):
        path = run_dir / f"{role}.json"
        path.write_text(json.dumps({"reference_demand": {"passed": True}}))
        files[role] = str(path)
    (run_dir / "events.jsonl").write_text(file_event_stream(files), encoding="utf-8")
    previous = {
        "id": job.id,
        "family_id": job.family_id,
        "paper": job.paper,
        "seed": 42,
        "model": "gemma4:12b",
        "provider": "ollama",
        "preview": False,
        "passed": True,
        "files": files,
        "errors": [],
        "duration_seconds": 1,
    }
    previous[changed] = {"model": "different:model", "seed": 100, "preview": True}.get(
        changed
    )
    previous["request_identity"] = request_identity(
        job,
        seed=previous["seed"],
        model=previous["model"],
        preview=previous["preview"],
    )
    previous["artifact_sha256"] = {
        role: _sha256(Path(path)) for role, path in files.items()
    }
    previous["events_sha256"] = _sha256(run_dir / "events.jsonl")
    if changed == "runtime":
        previous["request_identity"]["runtime_sha256"] = "stale-source"
    elif changed == "artifact":
        Path(files["question_paper"]).write_text("modified after qualification")
    elif changed == "role":
        files.pop("question_paper")
    elif changed == "events":
        (run_dir / "events.jsonl").write_text('{"type":"progress"}\n')
    (run_dir / "matrix-result.json").write_text(json.dumps(previous))
    monkeypatch.setattr(
        "tools.live_generation_matrix.run_backend",
        lambda command, **kwargs: BackendRun(1, False, "", "fresh attempt", 1000),
    )
    report = run_matrix(
        [job],
        output_root=tmp_path,
        command_prefix=["backend"],
        model="gemma4:12b",
        provider="ollama",
        ollama_url="http://localhost:11434",
        base_seed=42,
        timeout_seconds=30,
        dry_run=False,
        resume=True,
    )
    assert report["results"][0]["passed"] is False
    assert "fresh attempt" in report["results"][0]["errors"][0]


def test_matrix_persists_completed_routes_before_starting_the_next(
    tmp_path, monkeypatch
):
    selected = jobs()[:2]

    def fail(command, **kwargs):
        if command[command.index("--paper") + 1] == selected[1].paper:
            report = json.loads((tmp_path / "matrix-report.json").read_text())
            assert report["complete"] is False
            assert [item["id"] for item in report["results"]] == [selected[0].id]
        return BackendRun(1, False, "", "intentional fixture failure", 1000)

    monkeypatch.setattr("tools.live_generation_matrix.run_backend", fail)
    report = run_matrix(
        selected,
        output_root=tmp_path,
        command_prefix=["backend"],
        model="gemma4:12b",
        provider="ollama",
        ollama_url="http://localhost:11434",
        base_seed=42,
        timeout_seconds=30,
        dry_run=False,
        resume=False,
    )
    assert report["complete"] is True
    assert report["summary"]["failed"] == 2


def test_starting_a_retry_invalidates_old_success_before_launch(tmp_path, monkeypatch):
    job = jobs()[0]
    run_dir = tmp_path / job.backend_subject / f"paper-{job.paper}"
    run_dir.mkdir(parents=True)
    result_path = run_dir / "matrix-result.json"
    result_path.write_text(json.dumps({"passed": True}))
    report_path = tmp_path / "matrix-report.json"
    report_path.write_text(
        json.dumps({"complete": True, "results": [{"passed": True}]})
    )

    def check_state(command, **kwargs):
        assert json.loads(result_path.read_text())["passed"] is False
        assert json.loads(result_path.read_text())["status"] == "running"
        assert json.loads(report_path.read_text())["complete"] is False
        assert json.loads(report_path.read_text())["results"] == []
        return BackendRun(1, False, "", "fixture", 1000)

    monkeypatch.setattr("tools.live_generation_matrix.run_backend", check_state)
    run_matrix(
        [job],
        output_root=tmp_path,
        command_prefix=["backend"],
        model="gemma4:12b",
        provider="ollama",
        ollama_url="http://localhost:11434",
        base_seed=42,
        timeout_seconds=30,
        dry_run=False,
        resume=False,
    )


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
def test_interrupted_route_keeps_evidence_without_counting_a_verdict(
    tmp_path, monkeypatch, interruption
):
    selected = jobs()[:2]
    event = '{"type":"progress","stage":"authoring"}\n'

    def run(command, *, run_dir, **_kwargs):
        if command[command.index("--paper") + 1] == selected[0].paper:
            return BackendRun(1, False, "", "fixture failure", 1000)
        (run_dir / "events.jsonl").write_text(event)
        raise interruption(143)

    monkeypatch.setattr("tools.live_generation_matrix.run_backend", run)
    with pytest.raises(interruption):
        run_matrix(
            selected,
            output_root=tmp_path,
            command_prefix=["backend"],
            model="fixture",
            provider="ollama",
            ollama_url="http://127.0.0.1:1",
            base_seed=42,
            timeout_seconds=30,
            dry_run=True,
            resume=False,
        )

    job = selected[1]
    folder = tmp_path / job.backend_subject / f"paper-{job.paper}"
    result = json.loads((folder / "matrix-result.json").read_text())
    assert result["status"] == "interrupted"
    assert result["passed"] is False
    assert result["files"] == {}
    assert (folder / "events.jsonl").read_text() == event
    assert result["events_sha256"] == _sha256(folder / "events.jsonl")
    manifest = json.loads(Path(result["qualification_manifest"]).read_text())
    assert manifest["gate_results"]["generation"] == "not_run"
    assert manifest["evidence"][0]["sha256"] == result["events_sha256"]
    report = json.loads((tmp_path / "matrix-report.json").read_text())
    assert report["complete"] is False
    assert report["summary"] == {"papers": 1, "passed": 0, "failed": 1}


@pytest.mark.parametrize("drift", ["model", "runtime", "artifact", "unknown_model"])
def test_final_matrix_rechecks_earlier_evidence(tmp_path, monkeypatch, drift):
    selected = jobs()[:2]
    current = {
        "model": None if drift == "unknown_model" else "original-model",
        "runtime": "original-source",
    }
    first_question = []
    monkeypatch.setattr(
        "tools.live_generation_matrix._model_digest", lambda *args: current["model"]
    )
    monkeypatch.setattr(
        "tools.live_generation_matrix._runtime_sha256",
        lambda: current["runtime"],
        raising=False,
    )

    def complete(command, *, run_dir, **kwargs):
        paper = command[command.index("--paper") + 1]
        job = next(item for item in selected if item.paper == paper)
        files = published_files(run_dir, job, seed=42 + job.seed_offset)
        if job == selected[0]:
            first_question.append(Path(files["question_paper"]))
        if job == selected[1]:
            if drift == "model":
                current["model"] = "replacement-model"
            elif drift == "runtime":
                current["runtime"] = "changed-source"
            elif drift == "artifact":
                first_question[0].write_text("tampered")
        return BackendRun(0, False, file_event_stream(files), "", 1000)

    monkeypatch.setattr("tools.live_generation_matrix.run_backend", complete)
    report = run_matrix(
        selected,
        output_root=tmp_path,
        command_prefix=["backend"],
        model="gemma4:12b",
        provider="ollama",
        ollama_url="http://localhost:11434",
        base_seed=42,
        timeout_seconds=30,
        dry_run=False,
        resume=False,
    )
    assert report["complete"] is True
    assert report["results"][0]["passed"] is False
    assert report["results"][0]["errors"]
