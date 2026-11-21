import io
import json
import signal
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest


def test_public_cli_defaults_to_model_authored_french():
    from Backend.Core.cli import build_parser

    args = build_parser().parse_args(
        [
            "generate-assessment",
            "--assessment",
            "fr-bac-general-nsi-written-2027",
            "--reference-index",
            "references.sqlite",
            "--seed",
            "42",
        ]
    )
    assert args.provider == "ollama"
    assert args.authoring_version == "v36"


@pytest.mark.parametrize("model", ["fixture:cloud", "fixture:preview-cloud"])
def test_french_cli_reports_cloud_route_before_model_identity(
    tmp_path, monkeypatch, capsys, model
):
    from Backend.Core.france import runtime
    from bridge import main

    def forbidden(*args, **kwargs):
        pytest.fail("A cloud-tagged model must not reach the Ollama API")

    monkeypatch.setattr(runtime, "open_ollama_request", forbidden)
    index = tmp_path / "references.sqlite"
    index.touch()
    output = tmp_path / "output"
    assert (
        main(
            [
                "generate-assessment",
                "--assessment",
                "fr-bac-general-nsi-written-2027",
                "--reference-index",
                str(index),
                "--seed",
                "42",
                "--model",
                model,
                "--output",
                str(output),
            ]
        )
        == 1
    )
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "local_ollama_cloud_route"
    assert not any(event["type"] in {"file", "done"} for event in events)
    assert not output.exists()


@pytest.mark.parametrize(
    "provider", ["ollama", "apple", "openai", "anthropic", "deepseek"]
)
def test_new_public_route_never_calls_the_catalogue(monkeypatch, provider):
    from Backend.Core.france import llm_runtime, runtime

    seen = []
    monkeypatch.setattr(
        llm_runtime,
        "handle_generate_llm_assessment",
        lambda args: seen.append(args) or 7,
    )
    monkeypatch.setattr(
        runtime, "generate_assessment", lambda **kwargs: pytest.fail("catalogue called")
    )
    args = Namespace(provider=provider, authoring_version="v36")
    assert runtime.handle_generate_assessment(args) == 7
    assert seen == [args]


@pytest.fixture
def publication(tmp_path, monkeypatch):
    from Backend.Core.france import llm_runtime
    from tests.test_french_llm_pipeline import Client
    from tests.test_nsi_pipeline import make_index

    index = tmp_path / "references.sqlite"
    make_index(index)
    args = Namespace(
        assessment="fr-bac-general-nsi-written-2027",
        provider="ollama",
        model="mock-model",
        seed=42,
        reference_index=index,
        output=tmp_path / "private-output",
        ollama_url="http://localhost:11434",
        large_print=False,
        api_key="",
    )
    events = []

    class PublicationClient(Client):
        def generate_request(self, request):
            if "findings" in request.schema["properties"]:
                return {"findings": []}
            return super().generate_request(request)

    monkeypatch.setattr(
        llm_runtime, "HostedLLMClient", lambda **kwargs: PublicationClient()
    )
    monkeypatch.setattr(llm_runtime, "_model_snapshot", lambda args: "a" * 64)
    monkeypatch.setattr(
        "Backend.Core.ollama_admission.require_local_ollama_capacity",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        llm_runtime,
        "emit",
        lambda kind, **fields: events.append({"type": kind, **fields}),
    )
    return llm_runtime, args, events


def test_french_whole_paper_rejection_prevents_publishing(publication, monkeypatch):
    subject, args, events = publication
    from tests.test_french_llm_pipeline import Client

    class RefusingReview(Client):
        def generate_request(self, request):
            if "findings" in request.schema["properties"]:
                return {
                    "findings": [
                        {
                            "kind": "answer_leakage",
                            "target_id": "missing",
                            "peer_id": "also-missing",
                            "target_quote": "Example visible clue",
                            "peer_quote": "Example answer",
                            "reason": "The stated clue provides the answer.",
                        }
                    ]
                }
            return super().generate_request(request)

    monkeypatch.setattr(subject, "HostedLLMClient", lambda **_: RefusingReview())
    assert subject.handle_generate_llm_assessment(args) == 1, events
    assert not any(event["type"] == "file" for event in events)
    assert not list(args.output.glob("nsi-2027-v36-*"))


def test_french_whole_paper_repair_keeps_other_exercises(publication, monkeypatch):
    from tests.test_french_llm_pipeline import Client

    subject, args, events = publication

    class RepairClient(Client):
        review_count = 0

        def generate_request(self, request):
            if "findings" in request.schema["properties"]:
                self.review_count += 1
                if self.review_count == 2:
                    assert "Nouvelle variante" in request.prompt
                    return {"findings": []}
                first = json.loads(request.prompt.rsplit("\n", 1)[-1])[0]
                return {
                    "findings": [
                        {
                            "kind": "credit_mismatch",
                            "target_id": first["id"],
                            "peer_id": first["id"],
                            "target_quote": first["prompt"],
                            "peer_quote": first["mark_scheme"].splitlines()[0],
                            "reason": "Le barème demande une autre justification.",
                        }
                    ]
                }
            response = super().generate_request(request)
            if request.prompt.startswith("NOUVELLE_RÉDACTION:"):
                assert response["id"] == "1"
                response["questions"][0]["prompt"] += " Nouvelle variante."
            return response

    client = RepairClient()
    monkeypatch.setattr(subject, "HostedLLMClient", lambda **_: client)
    assert subject.handle_generate_llm_assessment(args) == 0, events
    path = next(
        Path(event["path"])
        for event in events
        if event.get("role") == "assessment_package"
    )
    package = json.loads(path.read_text())
    subject.llm_pipeline.validate_package(package)
    assert client.review_count == 2
    assert [history["accepted_round"] for history in package["exercise_attempts"]] == [
        2,
        1,
        1,
    ]
    assert package["exercises"][1:] == package["paper_review_baseline"]["exercises"][1:]
    # Recomputing the outer digest does not make an invented finding replayable.
    refusal = package["exercise_attempts"][0]["rounds"][0]["refusal"]
    refusal["findings"][0]["target_quote"] = (
        "Cette citation ne figure pas dans le sujet."
    )
    package["identity"]["content_sha256"] = subject.llm_pipeline._digest(
        {key: value for key, value in package.items() if key != "identity"}
    )
    with pytest.raises(ValueError, match="source evidence"):
        subject.llm_pipeline.validate_package(package)


def test_local_memory_refusal_has_a_distinct_terminal_code(publication, monkeypatch):
    from Backend.Core.ollama_admission import ResourceAdmissionError

    subject, args, events = publication

    def refuse(*args, **kwargs):
        raise ResourceAdmissionError("Local memory preflight refused the request.")

    monkeypatch.setattr(subject.llm_pipeline, "generate", refuse)
    assert subject.handle_generate_llm_assessment(args) == 1
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "local_memory_unavailable"
    assert not any(event["type"] in {"done", "file"} for event in events)


@pytest.mark.parametrize("provider", ["openai", "anthropic", "deepseek"])
def test_blank_hosted_credentials_stop_before_preflight(
    publication, monkeypatch, provider
):
    subject, args, events = publication
    args.provider = provider
    args.api_key = " \t"

    def create_client(**kwargs):
        pytest.fail("French hosted client must not be created for a blank key")

    monkeypatch.setattr(subject, "HostedLLMClient", create_client)
    assert subject.handle_generate_llm_assessment(args) == 1
    assert events[-1]["type"] == "error"
    assert "Ajoutez la clé" in events[-1]["message"]
    assert not args.output.exists()


def test_pasted_hosted_key_is_removed_from_failure_evidence(publication, monkeypatch):
    from Backend.Core.generation_diagnostics import GenerationEvidenceError

    subject, args, events = publication
    args.provider = "openai"
    key = "fixture-only-not-a-real-key"
    args.api_key = f" {key}\t"
    create_client = subject.HostedLLMClient

    def checked_client(**kwargs):
        assert kwargs["api_key"] == key
        return create_client(**kwargs)

    def reject(*args, **kwargs):
        assert kwargs["record_round"].secrets == (key,)
        raise GenerationEvidenceError(
            f"Fixture refusal for {key}", details={"rejected": key}
        )

    monkeypatch.setattr(subject, "HostedLLMClient", checked_client)
    monkeypatch.setattr(subject.llm_pipeline, "generate", reject)
    assert subject.handle_generate_llm_assessment(args) == 1
    [diagnostic] = (args.output / ".keldin-diagnostics").glob("failure-*.json")
    assert json.loads(diagnostic.read_text())["details"]["rejected"] == "[redacted]"
    assert events[-1]["message"] == "Fixture refusal for [redacted]"


@pytest.mark.parametrize(
    ("input_tokens", "reason", "expected_code"),
    [
        (14_000, "context_capacity", "french_model_context_unavailable"),
        (None, "context_capacity", "french_model_context_unavailable"),
        (5_000, "provider_structure", "french_generation_failed"),
    ],
)
def test_public_ollama_context_refusal_preserves_distinct_reason(
    publication, monkeypatch, input_tokens, reason, expected_code
):
    from Backend.Core import providers

    subject, args, events = publication
    monkeypatch.setattr(subject, "HostedLLMClient", providers.HostedLLMClient)
    monkeypatch.setattr(providers, "require_local_ollama_capacity", lambda *_: None)
    requests = []

    def transport(url, payload, _headers, **_options):
        endpoint = url.rsplit("/", 1)[-1]
        requests.append(endpoint)
        if endpoint == "show":
            return io.BytesIO(b'{"capabilities":["completion"]}')
        assert endpoint == "chat"
        request = json.loads(payload)
        assert request["truncate"] is False and request["shift"] is False
        return io.BytesIO(
            json.dumps(
                {
                    "done": True,
                    "done_reason": "stop",
                    "message": {"role": "assistant", "content": "not valid JSON"},
                    "prompt_eval_count": input_tokens,
                    "eval_count": 3,
                }
            ).encode()
        )

    monkeypatch.setattr(providers, "urllib_request", transport)
    assert subject.handle_generate_llm_assessment(args) == 1
    assert requests == ["show", "chat"]
    assert not list(args.output.rglob("*.pdf"))
    assert [event["type"] for event in events] == ["error"]
    assert events[0]["code"] == expected_code
    assert "not valid JSON" not in events[0]["message"]
    (report,) = (args.output / ".keldin-diagnostics").glob("failure-*.json")
    evidence = json.loads(report.read_text(encoding="utf-8"))["details"]
    assert evidence["kind"] == reason
    assert evidence["raw_response"] == "not valid JSON"


def test_invalid_authored_table_stays_in_private_diagnostics(publication, monkeypatch):
    from tests.test_french_llm_pipeline import Client

    subject, args, events = publication
    private_marker = "PRIVATE_SYNTHETIC_TABLE_TITLE"

    def invalidate(raw):
        table = raw["materials"][0]
        table["title"] = private_marker
        table["rows"][0][1] = ""

    client = Client(mutate=invalidate)
    monkeypatch.setattr(subject, "HostedLLMClient", lambda **kwargs: client)
    assert subject.handle_generate_llm_assessment(args) == 1
    assert len(client.requests) == 2
    assert events[-1]["type"] == "error"
    assert private_marker not in events[-1]["message"]
    assert events[-1]["code"] == "french_authoring_structure"
    assert "Aucun sujet" in events[-1]["message"]
    assert not any(event["type"] in {"done", "file"} for event in events)
    assert not list(args.output.rglob("*.pdf"))
    (report,) = (args.output / ".keldin-diagnostics").glob("failure-*.json")
    details = json.loads(report.read_text(encoding="utf-8"))["details"]
    assert details["kind"] == "french_authoring_structure"
    assert len(details["attempts"]) == 2
    assert all(private_marker in row["raw_response"] for row in details["attempts"])


def test_ollama_memory_refusal_precedes_authoring(publication, monkeypatch):
    from Backend.Core.ollama_admission import ResourceAdmissionError

    subject, args, events = publication
    calls = []

    def refuse(url, model):
        calls.append((url, model))
        raise ResourceAdmissionError("Not enough memory")

    monkeypatch.setattr(
        "Backend.Core.ollama_admission.require_local_ollama_capacity", refuse
    )
    monkeypatch.setattr(
        subject.llm_pipeline,
        "generate",
        lambda **kwargs: pytest.fail("Authoring started"),
    )
    assert subject.handle_generate_llm_assessment(args) == 1
    assert calls == [(args.ollama_url, args.model)]
    assert [event.get("code") for event in events] == ["local_memory_unavailable"]
    assert not args.output.exists()


@pytest.mark.parametrize("workers", [1, 2])
def test_mlx_memory_refusal_precedes_model_hashing(publication, monkeypatch, workers):
    from types import SimpleNamespace

    from Backend.Core import mlx_setup
    from Backend.Core.ollama_admission import ResourceAdmissionError

    subject, args, events = publication
    args.provider = "apple"
    model_path = args.reference_index.parent / "cached-model"
    monkeypatch.setattr(
        subject,
        "HostedLLMClient",
        lambda **_kwargs: SimpleNamespace(parallel_generation_workers=workers),
    )
    monkeypatch.setattr(mlx_setup, "resolve_local_mlx_model", lambda _model: model_path)
    monkeypatch.setattr(
        subject, "_model_snapshot", lambda _args: pytest.fail("Model was hashed")
    )
    called = []

    def refuse(path, *, workers):
        called.append((path, workers))
        raise ResourceAdmissionError("Not enough memory")

    monkeypatch.setattr(mlx_setup, "ensure_mlx_memory_capacity", refuse)
    assert subject.handle_generate_llm_assessment(args) == 1
    assert called == [(model_path, workers)]
    assert [event.get("code") for event in events] == ["local_memory_unavailable"]
    assert not args.output.exists()


def test_cancellation_during_model_snapshot_is_reported(publication, monkeypatch):
    subject, args, events = publication
    previous = signal.getsignal(signal.SIGTERM)

    def cancel_during_snapshot(_args):
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler) and handler is not previous
        handler(signal.SIGTERM, None)
        pytest.fail("SIGTERM handler did not stop generation")

    monkeypatch.setattr(subject, "_model_snapshot", cancel_during_snapshot)
    assert subject.handle_generate_llm_assessment(args) == 130
    assert signal.getsignal(signal.SIGTERM) is previous
    assert [event.get("code") for event in events] == ["cancelled"]
    assert not args.output.exists()


def test_real_sigterm_during_french_preflight_has_cancelled_terminal_event(tmp_path):
    index = tmp_path / "references.sqlite"
    index.touch()
    output = tmp_path / "output"
    script = """
import os
import signal
import sys
from argparse import Namespace
from pathlib import Path
from Backend.Core.france import llm_runtime

def cancel_during_snapshot(_args):
    os.kill(os.getpid(), signal.SIGTERM)
    raise AssertionError("SIGTERM did not interrupt the snapshot")

llm_runtime._model_snapshot = cancel_during_snapshot
raise SystemExit(llm_runtime.handle_generate_llm_assessment(Namespace(
    assessment="fr-bac-general-nsi-written-2027",
    provider="ollama", model="test-only", seed=42,
    ollama_url="http://localhost:11434",
    reference_index=Path(sys.argv[1]), output=Path(sys.argv[2]),
)))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(index), str(output)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 130, result.stderr
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert [event["type"] for event in events] == ["error"]
    assert events[0]["code"] == "cancelled"
    assert not output.exists()


@pytest.mark.parametrize("large_print", [False, True])
def test_real_pdf_publication_keeps_model_identity_and_private_evidence(
    publication, large_print
):
    subject, args, events = publication
    args.large_print = large_print
    assert subject.handle_generate_llm_assessment(args) == 0, events
    files = {
        event["role"]: Path(event["path"])
        for event in events
        if event["type"] == "file"
    }
    assert set(files) == {
        "question_paper",
        "mark_scheme",
        "assessment_package",
        "package_manifest",
    }
    assert all(path.is_file() for path in files.values())
    manifest = json.loads(files["package_manifest"].read_text())
    assert manifest["identity"]["model"] == args.model
    assert manifest["identity"]["seed"] == args.seed
    assert manifest["model_used"] is True
    assert manifest["model_snapshot_sha256"] == "a" * 64
    assert manifest["teacher_review"] == manifest["empirical_calibration"] == "not_run"
    assert manifest["large_print"] is large_print
    assert manifest["identity"]["large_print"] is large_print
    assert manifest["identity"]["layout_policy"] == "fr-nsi-v36-code-layout-v1"
    assert (
        manifest["identity"]["authoring_schema_policy"]
        == subject.llm_pipeline.PRINTED_SQL_KEYS_AUTHORING_POLICY
    )
    assert manifest["warnings"]
    assert manifest["generation_limits"]["started_requests"] == 10
    assert manifest["generation_limits"]["completed_requests"] == 10
    assert manifest["generation_limits"]["max_requests"] == 24
    assert manifest["whole_paper_review"] == {
        "status": "passed",
        "content_sha256": manifest["identity"]["content_sha256"],
    }
    assert not list(args.output.glob(".nsi-llm-*"))
    assert events[-1]["type"] == "done"
    recovery = list((args.output / ".keldin-recovery").glob("*.json"))
    assert len(recovery) == 1
    snapshot = json.loads(recovery[0].read_text())["snapshot"]
    assert snapshot["state"] == "review_complete"
    assert len(snapshot["exercise_attempts"]) == 3


def test_recovery_cleanup_warning_is_reported_without_failing_publication(
    publication, monkeypatch
):
    subject, args, events = publication
    notices = []
    monkeypatch.setattr(
        subject, "emit_progress", lambda message, **kwargs: notices.append(message)
    )

    class Recorder:
        retention_warning = "Cleanup could not be confirmed."

        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, snapshot):
            pass

    monkeypatch.setattr(subject, "RecoveryEvidenceRecorder", Recorder)
    assert subject.handle_generate_llm_assessment(args) == 0
    path = next(
        Path(event["path"])
        for event in events
        if event.get("role") == "package_manifest"
    )
    manifest = json.loads(path.read_text())
    assert any("anciens" in warning for warning in manifest["operational_warnings"])
    assert any("anciens" in message for message in notices)
    assert all(isinstance(warning, dict) for warning in manifest["warnings"])


@pytest.mark.parametrize("change", ["missing", "mismatch"])
def test_live_runtime_requires_selected_layout_even_for_legacy_readable_package(
    publication, monkeypatch, change
):
    subject, args, events = publication
    original = subject.llm_pipeline.generate

    def wrong_layout(**kwargs):
        package = original(**kwargs)
        if change == "missing":
            package["identity"].pop("layout_policy")
            package["identity"].pop("large_print")
        else:
            package["identity"]["large_print"] = True
        return package

    monkeypatch.setattr(subject.llm_pipeline, "generate", wrong_layout)
    assert subject.handle_generate_llm_assessment(args) == 1
    assert not any(event["type"] in {"file", "done"} for event in events)


def test_render_failure_never_publishes_partial_output(publication, monkeypatch):
    subject, args, events = publication

    def fail(*args, **kwargs):
        raise ValueError("Corrigé illisible")

    monkeypatch.setattr(subject, "validate_llm_pdf", fail)
    assert subject.handle_generate_llm_assessment(args) == 1
    assert not any(event["type"] in {"file", "done"} for event in events)
    assert not list(args.output.glob(".nsi-llm-*"))
    assert not list(args.output.rglob("*.pdf"))


def test_elapsed_limit_is_checked_again_before_publication(publication, monkeypatch):
    from Backend.Core.france import generation_budget

    subject, args, events = publication
    now = [0.0]
    monkeypatch.setattr(generation_budget.time, "monotonic", lambda: now[0])
    original = subject.atomic_json

    def expire_after_manifest(path, data):
        original(path, data)
        if path.name == "manifest.json":
            now[0] = generation_budget.MAX_ELAPSED_SECONDS + 1

    monkeypatch.setattr(subject, "atomic_json", expire_after_manifest)
    assert subject.handle_generate_llm_assessment(args) == 1
    assert not any(event["type"] in {"file", "done"} for event in events)
    assert not list(args.output.glob(".nsi-llm-*"))
    assert not list(args.output.rglob("*.pdf"))


def test_hosted_charge_notice_precedes_first_generation_request(
    publication, monkeypatch
):
    from tests.test_french_llm_pipeline import Client

    subject, args, events = publication
    args.provider = "deepseek"
    args.api_key = "test-only-key"
    notices = []
    monkeypatch.setattr(
        subject, "emit_progress", lambda message, **kwargs: notices.append(message)
    )

    class HostedFixture(Client):
        provider = "deepseek"

        def generate_request(self, request):
            assert any("24" in message and "frais" in message for message in notices)
            if "findings" in request.schema["properties"]:
                return {"findings": []}
            return super().generate_request(request)

    monkeypatch.setattr(subject, "HostedLLMClient", lambda **kwargs: HostedFixture())
    assert subject.handle_generate_llm_assessment(args) == 0, events


def test_different_actual_model_is_not_published_under_requested_identity(
    publication, monkeypatch
):
    subject, args, events = publication
    from tests.test_french_llm_pipeline import Client

    client = Client()
    client.model = "different-model"
    monkeypatch.setattr(subject, "HostedLLMClient", lambda **kwargs: client)
    assert subject.handle_generate_llm_assessment(args) == 1
    assert "modèle" in events[-1]["message"]
    assert not any(event["type"] in {"file", "done"} for event in events)


def test_cancelled_model_call_never_publishes_a_draft(publication, monkeypatch):
    subject, args, events = publication

    def cancel(**kwargs):
        raise InterruptedError("Création annulée")

    monkeypatch.setattr(subject.llm_pipeline, "generate", cancel)
    assert subject.handle_generate_llm_assessment(args) == 130
    assert events[-1]["code"] == "cancelled"
    assert not any(event["type"] in {"file", "done"} for event in events)


@pytest.mark.parametrize("changed", ["model", "source", "references"])
def test_changed_generation_inputs_prevent_publication(
    publication, monkeypatch, changed
):
    subject, args, events = publication
    if changed == "model":
        values = iter(["a" * 64, "b" * 64])
        monkeypatch.setattr(subject, "_model_snapshot", lambda args: next(values))
    elif changed == "source":
        values = iter([subject.implementation_identity(), "b" * 64])
        monkeypatch.setattr(subject, "implementation_identity", lambda: next(values))
    else:
        original = subject._file_hash
        calls = 0

        def changed_hash(path):
            nonlocal calls
            if path == args.reference_index:
                calls += 1
                return str(calls) * 64
            return original(path)

        monkeypatch.setattr(subject, "_file_hash", changed_hash)
    assert subject.handle_generate_llm_assessment(args) == 1
    assert "ont changé" in events[-1]["message"]
    assert not any(event["type"] in {"file", "done"} for event in events)
    assert not list(args.output.rglob("*.pdf"))
