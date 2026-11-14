"""Load trusted, registry-declared family entry points."""

from __future__ import annotations

import inspect
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from Backend.Core.family_contracts import ProgressCallback
    from Backend.Core.json_client import JSONGenerationClient

EntryPointContract = Literal["keywords-v1", "request-v1"]
EntryPoint = Callable[..., dict[str, Path]]


@dataclass(frozen=True, slots=True, kw_only=True)
class FamilyGenerationRequest:
    paper: str
    syllabus_path: Path
    output_dir: Path
    seed: int | None
    model: str
    ollama_url: str
    dry_run: bool
    progress: ProgressCallback | None = None
    client: JSONGenerationClient | None = field(default=None, repr=False)
    checkpoint_path: Path | None = None
    notes_source: Path | None = None


def parse_entry_point_contract(value: object) -> EntryPointContract:
    if value == "keywords-v1":
        return "keywords-v1"
    if value == "request-v1":
        return "request-v1"
    raise ValueError("unsupported generator entry-point contract")


def load_generator_entry_point(python_root: Path, entry_point: str) -> EntryPoint:
    module_name, separator, function_name = entry_point.partition(":")
    if not separator or not module_name or not function_name:
        raise ValueError(f"invalid generator entry point: {entry_point}")

    import_path = str(python_root)
    if import_path not in sys.path:
        sys.path.insert(0, import_path)
    function: object = getattr(import_module(module_name), function_name, None)
    if not callable(function):
        raise TypeError(f"generator entry point is not callable: {entry_point}")
    return cast(EntryPoint, function)


def bind_generator_entry_point(
    entry_point: EntryPoint,
    request: FamilyGenerationRequest,
    *,
    contract: EntryPointContract,
    family_id: str,
    uses_ai: bool,
) -> Callable[[], dict[str, Path]]:
    if contract == "request-v1":
        return partial(entry_point, request)
    return partial(
        entry_point, **_legacy_arguments(entry_point, request, family_id, uses_ai)
    )


def _legacy_arguments(
    entry_point: EntryPoint,
    request: FamilyGenerationRequest,
    family_id: str,
    uses_ai: bool,
) -> dict[str, Any]:
    parameters = inspect.signature(entry_point).parameters
    candidates: dict[str, Any] = {
        "paper": request.paper,
        "syllabus_path": request.syllabus_path,
        "output_dir": request.output_dir,
        "seed": request.seed,
        "model": request.model,
        "ollama_url": request.ollama_url,
        "dry_run": request.dry_run,
        "progress": request.progress,
        "checkpoint_path": request.checkpoint_path,
    }
    if request.notes_source is not None:
        candidates["notes_source"] = request.notes_source
    if uses_ai:
        candidates["client"] = request.client
    arguments = {
        name: value for name, value in candidates.items() if name in parameters
    }
    missing = [
        name
        for name, parameter in parameters.items()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind
        in {inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
        and name not in arguments
    ]
    if missing:
        raise RuntimeError(
            f"{family_id} entry point requires unsupported arguments: {missing}"
        )
    return arguments
