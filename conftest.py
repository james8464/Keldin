# Run each generator's tests from its resource root and expose all family packages.

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
ECONOMICS_ROOT = ROOT / "Resources" / "economics" / "edexcel-a" / "generator"
AQA_ECONOMICS_ROOT = ROOT / "Resources" / "economics" / "aqa" / "generator"
OCR_ECONOMICS_ROOT = ROOT / "Resources" / "economics" / "ocr" / "generator"
COMPUTER_SCIENCE_ROOT = ROOT / "Resources" / "computer-science" / "aqa" / "generator"
OCR_COMPUTER_SCIENCE_ROOT = (
    ROOT / "Resources" / "computer-science" / "ocr" / "generator"
)
BUSINESS_ROOT = ROOT / "Resources" / "business" / "aqa" / "generator"
ACCOUNTING_ROOT = ROOT / "Resources" / "accounting" / "aqa" / "generator"


@pytest.fixture
def mlx_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Give fake MLX loaders a weight file and deterministic memory sensors."""
    (tmp_path / "model.safetensors").write_bytes(b"fixture weights")
    monkeypatch.setattr(
        "Backend.Core.ollama_admission._memory_snapshot", lambda: (16 << 30, 1)
    )
    monkeypatch.setattr(
        "Backend.Core.ollama_admission._headroom_snapshot", lambda _: 8 << 30
    )
    return tmp_path


@pytest.fixture(autouse=True)
def generator_working_directory(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_path = Path(str(request.fspath)).resolve()
    if ECONOMICS_ROOT in test_path.parents:
        working_directory = ECONOMICS_ROOT
    elif AQA_ECONOMICS_ROOT in test_path.parents:
        working_directory = AQA_ECONOMICS_ROOT
    elif OCR_ECONOMICS_ROOT in test_path.parents:
        working_directory = OCR_ECONOMICS_ROOT
    elif COMPUTER_SCIENCE_ROOT in test_path.parents:
        working_directory = COMPUTER_SCIENCE_ROOT
    elif OCR_COMPUTER_SCIENCE_ROOT in test_path.parents:
        working_directory = OCR_COMPUTER_SCIENCE_ROOT
    elif BUSINESS_ROOT in test_path.parents:
        working_directory = BUSINESS_ROOT
    elif ACCOUNTING_ROOT in test_path.parents:
        working_directory = ACCOUNTING_ROOT
    else:
        working_directory = ROOT

    monkeypatch.chdir(working_directory)
    python_path = os.pathsep.join(
        (
            str(ROOT),
            str(ECONOMICS_ROOT),
            str(AQA_ECONOMICS_ROOT),
            str(OCR_ECONOMICS_ROOT),
            str(COMPUTER_SCIENCE_ROOT),
            str(OCR_COMPUTER_SCIENCE_ROOT),
            str(BUSINESS_ROOT),
            str(ACCOUNTING_ROOT),
        )
    )
    monkeypatch.setenv("PYTHONPATH", python_path)
