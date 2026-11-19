# Read JSON evidence with one consistent decoding policy.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    """Read one UTF-8 JSON document.

    Decoding errors propagate as `json.JSONDecodeError` so callers keep their
    existing failure handling. Shape validation stays with the caller unless it
    uses `read_json_object`.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_object(path: Path) -> dict[str, Any]:
    """Read one JSON object, rejecting arrays and scalar documents."""
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value
