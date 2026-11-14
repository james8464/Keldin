from __future__ import annotations

import base64
import io
import json
from hashlib import sha256

import pymupdf
import pytest

from Backend.Core import custom_assessment_vision as vision
from Backend.Core.custom_assessment_evidence import LocalSource
from Backend.Core.ollama_admission import ResourceAdmissionError

LAYOUT = {
    "heading": "Practice paper",
    "columns": 1,
    "question_markers": ["1", "2(a)"],
    "response_space": ["ruled lines", "box"],
    "figures": ["table"],
}


@pytest.fixture
def source():
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((20, 30), "Private practice paper")
        return LocalSource("question-paper", pdf.tobytes())


def responses(monkeypatch, *, metadata=None, **changes):
    calls = []
    reply = {
        "model": "fixture:latest",
        "done": True,
        "done_reason": "stop",
        "message": {"role": "assistant", "content": json.dumps(LAYOUT)},
        **changes,
    }

    def open_request(request, *, timeout):
        body = json.loads(request.data)
        route = request.full_url.removeprefix("http://127.0.0.1:11434")
        calls.append((route, body, timeout))
        response = (
            (
                {"capabilities": ["vision", "completion"]}
                if metadata is None
                else metadata
            )
            if route == "/api/show"
            else reply
        )
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setattr(vision, "open_ollama_request", open_request)
    monkeypatch.setattr(vision, "require_local_ollama_capacity", lambda *_: None)
    return calls


def test_layout_uses_pixels_and_binds_original_source(monkeypatch, source):
    calls = responses(monkeypatch)
    result = vision.analyze_custom_source_page(source, 1, model="fixture:latest")
    assert result.document_sha256 == sha256(source.content).hexdigest()
    assert result.page == 1
    assert result.layout == LAYOUT
    show, chat = calls
    assert show[:2] == ("/api/show", {"model": "fixture:latest"})
    assert chat[0] == "/api/chat"
    (message,) = chat[1]["messages"]
    (raw,) = message["images"]
    assert base64.b64decode(raw).startswith(b"\x89PNG\r\n\x1a\n")
    assert "Private practice paper" not in message["content"]
    assert chat[1]["stream"] is False
    assert chat[1]["keep_alive"] == 0
    assert "tools" not in chat[1]


@pytest.mark.parametrize(
    "metadata",
    [
        [],
        {"capabilities": ["completion"]},
        {"capabilities": "vision"},
        {"capabilities": ["vision"], "remote_host": "https://ollama.com"},
        {"capabilities": ["vision"], "remote_model": "aliased-model"},
        {"capabilities": ["vision"], "remote_host": False},
    ],
)
def test_unverified_or_cloud_model_receives_no_pixels(monkeypatch, source, metadata):
    calls = responses(monkeypatch, metadata=metadata)
    with pytest.raises(ValueError):
        vision.analyze_custom_source_page(source, 1, model="fixture:latest")
    assert [route for route, _, _ in calls] == ["/api/show"]


@pytest.mark.parametrize(
    "model", ["fixture:cloud", "fixture:70b-cloud", "http://remote/fixture"]
)
def test_explicit_cloud_model_is_refused_before_request(monkeypatch, source, model):
    calls = responses(monkeypatch)
    with pytest.raises(ValueError):
        vision.analyze_custom_source_page(source, 1, model=model)
    assert not calls


def test_resource_refusal_sends_no_pixels_and_remains_actionable(monkeypatch, source):
    calls = responses(monkeypatch)

    def refuse(*_):
        raise ResourceAdmissionError("Insufficient local memory")

    monkeypatch.setattr(vision, "require_local_ollama_capacity", refuse)
    with pytest.raises(ResourceAdmissionError, match="memory"):
        vision.analyze_custom_source_page(source, 1, model="fixture:latest")
    assert [route for route, _, _ in calls] == ["/api/show"]


@pytest.mark.parametrize(
    "reply",
    [
        {"done": 1},
        {"done_reason": "length"},
        {"model": "different:latest"},
        {"remote_host": "https://ollama.com"},
        {"message": {"role": "tool", "content": json.dumps(LAYOUT)}},
        {
            "message": {
                "role": "assistant",
                "content": json.dumps({**LAYOUT, "columns": 0}),
            }
        },
        {"message": {"role": "assistant", "content": '{"columns":1,"columns":2}'}},
        {"message": {"role": "assistant", "content": "Text " + json.dumps(LAYOUT)}},
        {
            "message": {
                "role": "assistant",
                "content": json.dumps({**LAYOUT, "columns": 1.0}),
            }
        },
    ],
)
def test_invalid_model_output_is_not_layout_evidence(monkeypatch, source, reply):
    responses(monkeypatch, **reply)
    with pytest.raises(ValueError, match="layout"):
        vision.analyze_custom_source_page(source, 1, model="fixture:latest")


@pytest.mark.parametrize("changed", [True, False])
def test_cli_uses_only_the_inspected_source_version(
    monkeypatch, source, tmp_path, capsys, changed
):
    from Backend.Core.cli import main

    path = tmp_path / "private.pdf"
    path.write_bytes(source.content)
    calls = responses(monkeypatch)
    code = main(
        [
            "inspect-custom-page-layout",
            "--source",
            "question-paper",
            str(path),
            "--sha256",
            "0" * 64 if changed else sha256(source.content).hexdigest(),
            "--page",
            "1",
            "--model",
            "fixture:latest",
        ]
    )
    captured = capsys.readouterr()
    event = json.loads(captured.out.splitlines()[-1])
    assert str(path) not in captured.out + captured.err
    if changed:
        assert code == 1
        assert not calls
        assert event["code"] == "custom_layout_rejected"
    else:
        assert code == 0
        assert event["type"] == "custom_page_layout"
        assert event["sha256"] == sha256(source.content).hexdigest()
        assert event["layout"] == LAYOUT
