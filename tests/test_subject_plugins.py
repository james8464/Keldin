from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from Backend.Core.board_profiles import board_profile, board_profile_ids
from Backend.Core.subject_plugins import (
    SubjectValidation,
    discover_subject_plugin,
    subject_plugin_ids,
)


def test_catalogue_does_not_load_subject_engines() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from Backend.Core.generator_registry import generator_capabilities
from Backend.Core.subject_plugins import discover_subject_plugin, subject_plugin_ids

assert generator_capabilities()
assert "mathematics" in subject_plugin_ids()
assert not any(name.startswith("Backend.Core.subjects.") for name in sys.modules)
assert "sympy" not in sys.modules

assert discover_subject_plugin(" BIOLOGY ").id == "biology"
assert "Backend.Core.subjects.biology" in sys.modules
assert "Backend.Core.subjects.mathematics" not in sys.modules
assert "sympy" not in sys.modules

maths = discover_subject_plugin("mathematics")
assert discover_subject_plugin(" MATHEMATICS ") is maths
assert "sympy" in sys.modules
""",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("registry_first", [False, True])
def test_subject_import_order_preserves_discovery(registry_first: bool) -> None:
    # A clean interpreter prevents pytest's collection order from hiding cycles.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import importlib
import sys

subjects = {
    "biology": ("biology", "BiologyPlugin"),
    "chemistry": ("chemistry", "ChemistryPlugin"),
    "computer-science": ("computer_science", "ComputerSciencePlugin"),
    "history": ("essay", "EssaySubjectPlugin"),
    "mathematics": ("mathematics", "MathematicsPlugin"),
    "further-mathematics": ("mathematics", "FurtherMathematicsPlugin"),
    "physics": ("physics", "PhysicsPlugin"),
}
if sys.argv[1] == "True":
    importlib.import_module("Backend.Core.subject_plugins")
else:
    for module in dict.fromkeys(module for module, _ in subjects.values()):
        importlib.import_module(f"Backend.Core.subjects.{module}")
    assert "Backend.Core.subject_plugins" not in sys.modules
from Backend.Core.subject_plugins import (
    SubjectPlugin, SubjectValidation, discover_subject_plugin, subject_plugin_ids,
)

for identifier, (module, class_name) in subjects.items():
    plugin = discover_subject_plugin(identifier)
    subject = sys.modules[f"Backend.Core.subjects.{module}"]
    assert isinstance(plugin, getattr(subject, class_name)), identifier
    assert isinstance(plugin, SubjectPlugin), identifier
    validation = plugin.validate_item(None)
    assert isinstance(validation, SubjectValidation), identifier
    assert validation.passed is False, identifier
assert {
    "accounting", "biology", "business", "chemistry", "computer-science",
    "economics", "english-literature", "further-mathematics", "geography",
    "history", "mathematics", "physics", "psychology", "sociology",
} <= set(subject_plugin_ids())
""",
            str(registry_first),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_current_subject_and_board_plugins_are_discoverable() -> None:
    assert {
        "accounting",
        "business",
        "computer-science",
        "economics",
        "mathematics",
    } <= set(subject_plugin_ids())
    assert {"aqa", "cambridge-international", "ocr", "pearson-edexcel"} <= set(
        board_profile_ids()
    )

    plugin = discover_subject_plugin("economics")
    result = plugin.validate_item(
        {"question": "Explain one effect of a higher interest rate.", "marks": 4}
    )

    assert isinstance(result, SubjectValidation)
    assert result.passed is True
    assert board_profile("aqa").page_size == "A4"


@pytest.mark.parametrize(
    "identifier",
    ["../economics", "/tmp/plugin.py", "module:factory", "economics.py"],
)
def test_plugin_discovery_never_imports_arbitrary_paths(identifier: str) -> None:
    with pytest.raises(ValueError, match="unknown subject plugin"):
        discover_subject_plugin(identifier)


def test_board_profile_loader_rejects_traversal() -> None:
    with pytest.raises(ValueError, match="unknown board profile"):
        board_profile(str(Path("..") / "aqa"))
