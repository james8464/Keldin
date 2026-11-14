# Run each generator's tests from its resource root and expose all family packages.

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from tools.generator_development import generator_roots

ROOT = Path(__file__).resolve().parent
_GENERATOR_TESTS = pytest.StashKey[tuple[tuple[Path, ...], frozenset[Path]]]()
_SUBPROCESS_PATH = pytest.StashKey[str]()


def pytest_configure(config: pytest.Config) -> None:
    roots = generator_roots(ROOT)
    test_roots = tuple(root / "tests" for root in roots)
    missing = [str(root) for root in test_roots if not root.is_dir()]
    if missing:
        raise pytest.UsageError(
            "Missing advertised generator tests: " + ", ".join(missing)
        )
    ancestors = frozenset(parent for root in test_roots for parent in root.parents)
    config.stash[_GENERATOR_TESTS] = (test_roots, ancestors)
    python_path = tuple(map(str, (ROOT, *roots)))
    config.stash[_SUBPROCESS_PATH] = os.pathsep.join(python_path)
    added = [location for location in python_path if location not in sys.path]
    sys.path[:0] = added

    def clean_paths() -> None:
        for location in added:
            if location in sys.path:
                sys.path.remove(location)

    config.add_cleanup(clean_paths)


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    if not collection_path.is_relative_to(ROOT / "Resources"):
        return None
    test_roots, ancestors = config.stash[_GENERATOR_TESTS]
    if collection_path in ancestors or any(
        collection_path.is_relative_to(root) for root in test_roots
    ):
        return None
    return True


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
    test_path = request.path
    test_roots, _ = request.config.stash[_GENERATOR_TESTS]
    working_directory = next(
        (root.parent for root in test_roots if test_path.is_relative_to(root)), ROOT
    )
    monkeypatch.chdir(working_directory)
    monkeypatch.setenv("PYTHONPATH", request.config.stash[_SUBPROCESS_PATH])
