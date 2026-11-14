# Register and discover the supported subject validation engines.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache, partial
from typing import Any

from Backend.Core.subject_contracts import SubjectPlugin as SubjectPlugin
from Backend.Core.subject_contracts import SubjectValidation as SubjectValidation


# Safe baseline plugin for families with validation in their own contracts.
@dataclass(frozen=True)
class ContractSubjectPlugin:
    id: str

    def validate_item(self, item: Any) -> SubjectValidation:
        if not isinstance(item, dict):
            return SubjectValidation(False, ("item must be an object",))
        question = str(item.get("question", "")).strip()
        marks = item.get("marks")
        diagnostics: list[str] = []
        if not question:
            diagnostics.append("question text is required")
        if not isinstance(marks, int) or isinstance(marks, bool) or marks <= 0:
            diagnostics.append("marks must be a positive integer")
        return SubjectValidation(not diagnostics, tuple(diagnostics))

    def solve(self, item: Any) -> Any:
        if isinstance(item, dict) and "canonical_solution" in item:
            return item["canonical_solution"]
        raise ValueError(f"{self.id} item has no deterministic canonical solution")

    def render_visual(self, specification: Any) -> Any:
        if not isinstance(specification, dict) or "kind" not in specification:
            raise ValueError("visual specification must declare a kind")
        return specification

    def validate_scheme(self, item: Any, scheme: Any) -> SubjectValidation:
        if not isinstance(scheme, dict):
            return SubjectValidation(False, ("mark scheme must be an object",))
        points = scheme.get("mark_points")
        if not isinstance(points, list) or not points:
            return SubjectValidation(False, ("mark scheme requires mark points",))
        return SubjectValidation(True)

    def calibration_features(self, item: Any) -> dict[str, float | str]:
        payload = item if isinstance(item, dict) else {}
        return {
            "subject": self.id,
            "marks": float(payload.get("marks", 0)),
            "command": str(payload.get("command", "unknown")),
        }


def _biology() -> SubjectPlugin:
    from Backend.Core.subjects.biology import BiologyPlugin

    return BiologyPlugin()


def _chemistry() -> SubjectPlugin:
    from Backend.Core.subjects.chemistry import ChemistryPlugin

    return ChemistryPlugin()


def _computer_science() -> SubjectPlugin:
    from Backend.Core.subjects.computer_science import ComputerSciencePlugin

    return ComputerSciencePlugin()


def _essay(identifier: str) -> SubjectPlugin:
    from Backend.Core.subjects.essay import EssaySubjectPlugin

    return EssaySubjectPlugin(identifier)


def _further_mathematics() -> SubjectPlugin:
    from Backend.Core.subjects.mathematics import FurtherMathematicsPlugin

    return FurtherMathematicsPlugin()


def _mathematics() -> SubjectPlugin:
    from Backend.Core.subjects.mathematics import MathematicsPlugin

    return MathematicsPlugin()


def _physics() -> SubjectPlugin:
    from Backend.Core.subjects.physics import PhysicsPlugin

    return PhysicsPlugin()


# Keep imports explicit so the frozen helper includes the engines even though
# reading the catalogue does not load them.
_SUBJECT_FACTORIES: dict[str, Callable[[], SubjectPlugin]] = {
    "accounting": partial(ContractSubjectPlugin, "accounting"),
    "biology": _biology,
    "business": partial(ContractSubjectPlugin, "business"),
    "chemistry": _chemistry,
    "computer-science": _computer_science,
    "economics": partial(ContractSubjectPlugin, "economics"),
    "english-literature": partial(_essay, "english-literature"),
    "further-mathematics": _further_mathematics,
    "geography": partial(_essay, "geography"),
    "history": partial(_essay, "history"),
    "mathematics": _mathematics,
    "physics": _physics,
    "psychology": partial(_essay, "psychology"),
    "sociology": partial(_essay, "sociology"),
}


def _registered_identifier(identifier: str) -> str:
    normalized = identifier.strip().lower()
    if normalized not in _SUBJECT_FACTORIES:
        raise ValueError(f"unknown subject plugin: {identifier}")
    return normalized


def subject_plugin_ids() -> tuple[str, ...]:
    return tuple(sorted(_SUBJECT_FACTORIES))


def validate_subject_plugin(identifier: str) -> None:
    _registered_identifier(identifier)


@cache
def _load_subject_plugin(identifier: str) -> SubjectPlugin:
    return _SUBJECT_FACTORIES[identifier]()


def discover_subject_plugin(identifier: str) -> SubjectPlugin:
    return _load_subject_plugin(_registered_identifier(identifier))
