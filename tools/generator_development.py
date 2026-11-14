"""Use the generator registry for local dependency installation and testing."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generator_roots(repository: Path) -> tuple[Path, ...]:
    resources = (repository / "Resources").resolve()
    data = json.loads(
        (resources / "generator-registry.json").read_text(encoding="utf-8")
    )
    roots: dict[Path, None] = {}
    for family in data["families"]:
        advertised = family["advertised"]
        if not isinstance(advertised, bool):
            raise ValueError("Generator admission must be a boolean")
        if not advertised:
            continue
        relative = Path(family["python_path"])
        directory = (resources / relative).resolve()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not directory.is_relative_to(resources)
        ):
            raise ValueError(
                f"Generator directory must stay under Resources: {relative}"
            )
        if directory == resources or not (directory / "pyproject.toml").is_file():
            raise ValueError(f"No generator pyproject.toml at {directory}")
        roots[directory] = None
    if not roots:
        raise ValueError("No advertised generator directories")
    return tuple(roots)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=("build", "test"))
    arguments = parser.parse_args()
    try:
        roots = generator_roots(ROOT)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        parser.error(str(error))
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        str(ROOT / f"requirements-{arguments.environment}.txt"),
    ]
    for directory in roots:
        command.extend(("-e", str(directory)))
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
