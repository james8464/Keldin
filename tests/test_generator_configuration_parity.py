from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.generator_development import generator_roots

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "Resources/generator-registry.json").read_text())
GENERATOR_ROOTS = {
    Path("Resources") / family["python_path"]
    for family in REGISTRY["families"]
    if family["advertised"]
}


def test_targeted_generator_test_still_uses_repository_configuration(tmp_path):
    root = tmp_path / "project"
    for relative in (
        "conftest.py",
        "pytest.ini",
        "tools/generator_development.py",
        "Resources/generator-registry.json",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, path)
    for relative in GENERATOR_ROOTS:
        generator = root / relative
        (generator / "tests").mkdir(parents=True)
        shutil.copyfile(
            ROOT / relative / "pyproject.toml", generator / "pyproject.toml"
        )
    edexcel = root / "Resources/economics/edexcel-a/generator"
    target = edexcel / "tests/test_isolation.py"
    (edexcel / "fixture_subject.py").write_text("SOURCE = 'selected checkout'\n")
    target.write_text(
        "from pathlib import Path\n"
        "from fixture_subject import SOURCE\n"
        "def test_isolation():\n"
        "    assert SOURCE == 'selected checkout'\n"
        "    assert Path.cwd() == Path(__file__).resolve().parents[1]\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(target)],
        cwd=root,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


@pytest.mark.parametrize("has_family_tests", [True, False])
def test_registry_addition_needs_no_pytest_path_edits(tmp_path, has_family_tests):
    repository = tmp_path / "new exam"
    relative_root = Path("Resources/sample-board/new-exam/generator")
    generator_root = repository / relative_root
    (generator_root / "tests").mkdir(parents=True)
    (generator_root / "pyproject.toml").touch()
    for name in ("conftest.py", "pytest.ini", "tools/generator_development.py"):
        destination = repository / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    (repository / "Resources/generator-registry.json").write_text(
        json.dumps(
            {
                "families": [
                    {
                        "advertised": True,
                        "python_path": str(relative_root.relative_to("Resources")),
                    },
                    {
                        "advertised": False,
                        "python_path": "private/test-archive/generator",
                    },
                ]
            }
        )
    )
    (generator_root / "example_exam.py").write_text("EXAM_READY = True\n")
    (generator_root / "tests/test_new_exam.py").write_text(
        "from pathlib import Path\n"
        "import subprocess\n"
        "import sys\n"
        "from example_exam import EXAM_READY\n"
        "def test_new_exam():\n"
        "    assert EXAM_READY\n"
        "    assert Path.cwd() == Path(__file__).resolve().parents[1]\n"
        "    subprocess.run([sys.executable, '-c', 'import example_exam'], "
        "cwd=Path(__file__).parent, check=True, timeout=5)\n"
    )
    (repository / "tests").mkdir()
    (repository / "tests/test_root.py").write_text(
        "from pathlib import Path\n"
        "def test_root():\n"
        "    assert Path.cwd() == Path(__file__).resolve().parents[1]\n"
    )
    ignored_tests = repository / "Resources/private/test-archive/generator/tests"
    ignored_tests.mkdir(parents=True)
    (ignored_tests / "test_not_advertised.py").write_text(
        "raise AssertionError('unadvertised tests must not be collected')\n"
    )
    if not has_family_tests:
        (generator_root / "tests").rename(generator_root / "unregistered-tests")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=repository,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if has_family_tests:
        assert result.returncode == 0, result.stdout + result.stderr
        assert "2 passed" in result.stdout
    else:
        assert result.returncode == pytest.ExitCode.USAGE_ERROR
        assert "Missing advertised generator tests" in result.stderr


@pytest.mark.parametrize("environment", ["build", "test"])
def test_install_uses_advertised_generators_without_network(tmp_path, environment):
    repository = tmp_path / "fake repository with spaces"
    script = repository / "macOS/scripts/bootstrap_backend.sh"
    script.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "macOS/scripts/bootstrap_backend.sh", script)
    installer = repository / "tools/generator_development.py"
    installer.parent.mkdir()
    shutil.copyfile(ROOT / "tools/generator_development.py", installer)
    registry = repository / "Resources/generator-registry.json"
    registry.parent.mkdir()
    shutil.copyfile(ROOT / registry.relative_to(repository), registry)
    for relative_root in GENERATOR_ROOTS:
        generator = repository / relative_root
        generator.mkdir(parents=True)
        (generator / "pyproject.toml").touch()
    arguments = tmp_path / "pip-arguments"
    fake_pip = tmp_path / "pip.py"
    fake_pip.write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['BOOTSTRAP_ARGUMENTS']).write_text(json.dumps(sys.argv[1:]))\n"
    )
    fake_python = tmp_path / "fake-python"
    fake_python.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        '[[ "$1" == "-m" && "$2" == "venv" ]] || exit 91\n'
        'mkdir -p "$3/bin"\nln -s "$REAL_PYTHON" "$3/bin/python"\n'
    )
    fake_python.chmod(0o700)
    subprocess.run(
        ["bash", str(script)]
        if environment == "build"
        else [sys.executable, str(installer), environment],
        check=True,
        capture_output=True,
        timeout=10,
        env={
            **os.environ,
            "PYTHON": str(fake_python),
            "REAL_PYTHON": sys.executable,
            "PYTHONPATH": str(tmp_path),
            "BOOTSTRAP_ARGUMENTS": str(arguments),
        },
    )
    captured = json.loads(arguments.read_text())
    assert captured[:3] == [
        "install",
        "-r",
        str(repository / f"requirements-{environment}.txt"),
    ]
    assert captured[3::2] == ["-e"] * len(GENERATOR_ROOTS)
    installed = [Path(value).relative_to(repository) for value in captured[4::2]]
    assert len(installed) == len(set(installed))
    assert set(installed) == GENERATOR_ROOTS


@pytest.mark.parametrize("python_path", ["../outside", "/etc", "linked", "missing"])
def test_invalid_advertised_path_refuses_setup(tmp_path, python_path):
    resources = tmp_path / "Resources"
    resources.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "pyproject.toml").touch()
    (resources / "linked").symlink_to(outside, target_is_directory=True)
    (resources / "generator-registry.json").write_text(
        json.dumps({"families": [{"advertised": True, "python_path": python_path}]})
    )
    with pytest.raises(ValueError, match=r"under Resources|No generator pyproject"):
        generator_roots(tmp_path)
