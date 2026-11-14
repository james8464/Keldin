# Read the supported generator families and their declared qualification evidence.

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

from Backend.Core.board_profiles import board_profile as load_board_profile
from Backend.Core.generator_entry_points import (
    EntryPointContract,
    parse_entry_point_contract,
)
from Backend.Core.paths import REPO_ROOT
from Backend.Core.subject_plugins import validate_subject_plugin

REGISTRY_PATH = REPO_ROOT / "Resources" / "generator-registry.json"
KNOWN_PROVIDERS = frozenset(
    {"ollama", "openai", "anthropic", "apple", "apple_intelligence"}
)
KNOWN_CONTENT_MODES = frozenset({"deterministic", "ai-assisted"})
KNOWN_QUALIFICATION_STATES = frozenset(
    {"not_run", "passed", "failed", "not_applicable"}
)


@dataclass(frozen=True, slots=True)
class PaperQualification:
    engineering_validated: bool
    visually_calibrated: bool
    empirically_calibrated: bool
    evidence_by_level: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class PaperContract:
    output_roles: tuple[str, ...]
    gates: Mapping[str, bool]
    qualification: PaperQualification


@dataclass(frozen=True)
class CheckpointNamespace:
    identity_key: str
    version: str

    def apply(self, path: Path) -> Path:
        prefix = f"{self.version}."
        return (
            path if path.name.startswith(prefix) else path.with_name(prefix + path.name)
        )


@dataclass(frozen=True, slots=True)
class GeneratorCapability:
    manifest_version: int
    id: str
    backend_subject: str
    resource_path: str
    python_path: str
    package: str
    entry_point: str
    syllabus_path: str
    subject_plugin: str
    board_profile: str
    specification_version: str
    blueprint_version: str
    reference_demand_profile: str
    content_mode: str
    supported_providers: tuple[str, ...]
    paper_contracts: Mapping[str, PaperContract]
    checkpoint_namespace: CheckpointNamespace | None = None
    entry_point_contract: EntryPointContract = "keywords-v1"

    @property
    def uses_ai(self) -> bool:
        return self.content_mode == "ai-assisted"

    @property
    def papers(self) -> tuple[str, ...]:
        return tuple(self.paper_contracts)

    def paper_for(self, paper: str) -> PaperContract:
        try:
            return self.paper_contracts[paper]
        except KeyError as error:
            raise ValueError(
                f"{self.backend_subject} does not support paper {paper}"
            ) from error


@lru_cache(maxsize=1)
def generator_capabilities() -> Mapping[str, GeneratorCapability]:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") not in {2, 3, 4, 5}:
        raise ValueError(
            f"unsupported generator registry schema: {payload.get('schema_version')}"
        )
    result: dict[str, GeneratorCapability] = {}
    for raw in payload.get("families", []):
        if not raw.get("advertised"):
            continue
        capability = _capability(raw)
        if capability.backend_subject in result:
            raise ValueError(f"duplicate backend subject: {capability.backend_subject}")
        result[capability.backend_subject] = capability
    if not result:
        raise ValueError("generator registry has no advertised families")
    return MappingProxyType(result)


def generator_capability(subject: str) -> GeneratorCapability:
    try:
        return generator_capabilities()[subject]
    except KeyError as error:
        raise ValueError(f"unsupported subject: {subject}") from error


def generator_subjects() -> tuple[str, ...]:
    return tuple(generator_capabilities())


# National frameworks are not exam boards and never inherit UK AO policy.
def assessment_framework(identifier: str):
    from Backend.Core.education_context import NSI_2027

    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    frameworks = payload.get("assessment_frameworks", [])
    matches = [item for item in frameworks if item.get("id") == identifier]
    if payload.get("schema_version") != 5 or len(matches) != 1:
        raise ValueError(f"Unsupported assessment framework: {identifier}")
    if identifier != NSI_2027.id or matches[0].get("policy") != "fr-nsi-written-v1":
        raise ValueError(f"Unrecognised assessment policy: {identifier}")
    return NSI_2027


def _paper_contracts(raw: dict[str, Any]) -> Mapping[str, PaperContract]:
    family = raw["id"]
    records = raw.get("papers", [])
    papers = tuple(item["id"] for item in records)
    if not papers or papers != tuple(raw.get("declared_papers", [])):
        raise ValueError(f"{family} declared papers do not match paper records")
    if not all(
        isinstance(paper, str) and re.fullmatch(r"[A-Za-z0-9.-]+", paper)
        for paper in papers
    ):
        raise ValueError(f"{family} has an invalid paper ID")
    if len(set(papers)) != len(papers):
        raise ValueError(f"{family} has a duplicate paper ID")

    outputs = raw.get("outputs_by_paper")
    if not isinstance(outputs, dict) or outputs.keys() != set(papers):
        raise ValueError(f"{family} output declarations must match paper records")

    result: dict[str, PaperContract] = {}
    for paper, record in zip(papers, records, strict=True):
        roles = outputs[paper]
        if (
            not isinstance(roles, list)
            or not roles
            or not all(isinstance(role, str) and role.strip() for role in roles)
            or len(set(roles)) != len(roles)
        ):
            raise ValueError(f"{family} paper {paper} has invalid output roles")
        result[paper] = PaperContract(
            output_roles=tuple(roles),
            gates=_gate_flags(record.get("checks", record.get("gates", {}))),
            qualification=_paper_qualification(record),
        )
    return MappingProxyType(result)


def _gate_flags(value: object) -> Mapping[str, bool]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(passed, bool)
        for key, passed in value.items()
    ):
        raise ValueError("paper gate checks must be an object with boolean gate values")
    return MappingProxyType(dict(value))


def _capability(raw: dict[str, Any]) -> GeneratorCapability:
    paper_contracts = _paper_contracts(raw)
    mode = str(raw.get("content_mode", ""))
    if mode not in KNOWN_CONTENT_MODES:
        raise ValueError(f"{raw['id']} has unsupported content mode: {mode}")
    providers = tuple(str(item) for item in raw.get("supported_providers", []))
    unknown_providers = set(providers) - KNOWN_PROVIDERS
    if unknown_providers:
        raise ValueError(
            f"{raw['id']} has unknown providers: {sorted(unknown_providers)}"
        )
    if (mode == "ai-assisted") != bool(providers):
        raise ValueError(f"{raw['id']} AI mode and supported providers disagree")
    entry_point = str(raw.get("entry_point", ""))
    package = str(raw.get("package", ""))
    if not entry_point.startswith(f"{package}.") or ":" not in entry_point:
        raise ValueError(f"{raw['id']} has an invalid entry point")
    resource_path = _relative_path(raw, "resource_path")
    python_path = _relative_path(raw, "python_path")
    syllabus_path = _relative_path(raw, "syllabus_path")
    manifest_version = int(raw.get("manifest_version", 1))
    if manifest_version != 1:
        raise ValueError(f"{raw['id']} has an unsupported manifest version")
    legacy_subject = {
        "economics-a-2015": "economics",
    }.get(str(raw.get("subject", "")), str(raw.get("subject", "")))
    subject_plugin = str(raw.get("subject_plugin", legacy_subject)).strip()
    board_profile = str(raw.get("board_profile", raw.get("board", ""))).strip()
    specification_version = str(
        raw.get("specification_version", "legacy-registry-v3")
    ).strip()
    blueprint_version = str(raw.get("blueprint_version", "legacy-registry-v3")).strip()
    reference_demand_profile = (
        _relative_path(raw, "reference_demand_profile")
        if raw.get("reference_demand_profile")
        else ""
    )
    if raw.get("advertised") and mode == "ai-assisted" and not reference_demand_profile:
        raise ValueError(f"{raw['id']} is missing its reference demand profile")
    if not all(
        (subject_plugin, board_profile, specification_version, blueprint_version)
    ):
        raise ValueError(f"{raw['id']} has incomplete declarative capability metadata")
    validate_subject_plugin(subject_plugin)
    load_board_profile(board_profile)
    return GeneratorCapability(
        manifest_version=manifest_version,
        id=str(raw["id"]),
        backend_subject=str(raw["backend_subject"]),
        resource_path=resource_path,
        python_path=python_path,
        package=package,
        entry_point=entry_point,
        syllabus_path=syllabus_path,
        subject_plugin=subject_plugin,
        board_profile=board_profile,
        specification_version=specification_version,
        blueprint_version=blueprint_version,
        reference_demand_profile=reference_demand_profile,
        content_mode=mode,
        supported_providers=providers,
        paper_contracts=paper_contracts,
        checkpoint_namespace=_checkpoint_namespace(raw),
        entry_point_contract=parse_entry_point_contract(
            raw.get("entry_point_contract", "keywords-v1")
        ),
    )


def _checkpoint_namespace(raw: dict[str, Any]) -> CheckpointNamespace | None:
    if "checkpoint_namespace" not in raw:
        return None
    value = raw["checkpoint_namespace"]
    if isinstance(value, dict) and set(value) == {"identity_key", "version"}:
        key, version = value["identity_key"], value["version"]
        if (
            isinstance(key, str)
            and re.fullmatch(r"[a-z][a-z0-9_]{0,47}_source_binding_version", key)
            and isinstance(version, str)
            and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", version)
        ):
            return CheckpointNamespace(key, version)
    raise ValueError(f"{raw['id']} has an invalid checkpoint namespace")


def _paper_qualification(raw: dict[str, Any]) -> PaperQualification:
    payload = raw.get("qualification")
    if payload is None:
        gates = _gate_flags(raw.get("gates", {}))
        return PaperQualification(
            engineering_validated=gates.get("release", False),
            visually_calibrated=gates.get("visual", False),
            empirically_calibrated=gates.get("difficulty", False),
            evidence_by_level=MappingProxyType({}),
        )
    if not isinstance(payload, dict) or set(payload) != {
        "engineering",
        "visual",
        "empirical",
    }:
        raise ValueError(
            "paper qualification levels must be engineering, visual, empirical"
        )

    def level(name: str) -> tuple[str, tuple[str, ...]]:
        value = payload[name]
        if not isinstance(value, dict):
            raise TypeError(f"paper qualification {name} must be an object")
        state = str(value.get("state", ""))
        if state not in KNOWN_QUALIFICATION_STATES:
            raise ValueError(f"paper qualification {name} has invalid state: {state}")
        evidence = value.get("evidence", [])
        if not isinstance(evidence, list) or not all(
            isinstance(path, str) and path for path in evidence
        ):
            raise ValueError(f"paper qualification {name} evidence must be paths")
        return state, tuple(evidence)

    engineering, engineering_evidence = level("engineering")
    visual, visual_evidence = level("visual")
    empirical, empirical_evidence = level("empirical")
    # An inapplicable prerequisite can permit a later review, but does not mean
    # that validation or calibration was performed at that level.
    satisfied_states = {"passed", "not_applicable"}
    engineering_satisfied = engineering in satisfied_states
    visual_satisfied = visual in satisfied_states
    return PaperQualification(
        engineering_validated=engineering == "passed",
        visually_calibrated=visual == "passed" and engineering_satisfied,
        empirically_calibrated=(
            empirical == "passed" and engineering_satisfied and visual_satisfied
        ),
        evidence_by_level=MappingProxyType(
            {
                "engineering": engineering_evidence,
                "visual": visual_evidence,
                "empirical": empirical_evidence,
            }
        ),
    )


def _relative_path(raw: dict[str, Any], name: str) -> str:
    value = str(raw.get(name, ""))
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{raw['id']} has an unsafe {name}")
    return value
