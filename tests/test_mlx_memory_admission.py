"""Test MLX cold-load memory refusal without allocating real model weights."""

import sys
from argparse import Namespace
from types import ModuleType

import pytest

from Backend.Core import mlx_setup, ollama_admission, providers
from Backend.Core.ollama_admission import GIB, ResourceAdmissionError


@pytest.fixture
def fake_loader(monkeypatch, mlx_snapshot):
    calls = []
    module = ModuleType("mlx_lm")

    def load(path, **kwargs):
        calls.append((path, kwargs))
        return object(), object()

    module.load = load
    monkeypatch.setitem(sys.modules, "mlx_lm", module)
    monkeypatch.setattr(
        providers, "resolve_local_mlx_model", lambda _: str(mlx_snapshot)
    )
    return calls


@pytest.mark.parametrize("path", ["setup", "generation"])
def test_cold_load_refused_before_loader(monkeypatch, mlx_snapshot, fake_loader, path):
    with (mlx_snapshot / "model.safetensors").open("wb") as stream:
        stream.truncate(4 * GIB)
    monkeypatch.setattr(ollama_admission, "_headroom_snapshot", lambda _: GIB)
    with pytest.raises(ResourceAdmissionError, match="headroom"):
        if path == "setup":
            mlx_setup.load_mlx_model(str(mlx_snapshot), local_only=True)
        else:
            client = providers.HostedLLMClient(
                provider="apple", model="fixture", api_key=""
            )
            client._load_apple_model()
    assert not fake_loader


def test_setup_reports_memory_refusal_not_download_failure(
    monkeypatch, mlx_snapshot, fake_loader, capsys
):
    monkeypatch.setattr(mlx_setup, "validate_mlx_setup_environment", lambda **_: None)
    monkeypatch.setattr(mlx_setup, "mlx_runtime_available", lambda: True)
    monkeypatch.setattr(ollama_admission, "_headroom_snapshot", lambda _: GIB)
    args = Namespace(model=str(mlx_snapshot), local_only=True, revision=None)
    assert mlx_setup.handle_setup_mlx(args) == 1
    assert '"code": "local_memory_unavailable"' in capsys.readouterr().out
    assert not fake_loader


def test_two_workers_require_additional_headroom(monkeypatch, mlx_snapshot):
    monkeypatch.setattr(ollama_admission, "_headroom_snapshot", lambda _: 6 * GIB)
    ollama_admission.require_local_mlx_capacity(4 * GIB, workers=1)
    with pytest.raises(ResourceAdmissionError, match="headroom"):
        ollama_admission.require_local_mlx_capacity(4 * GIB, workers=2)
