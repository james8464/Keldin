# Read and validate the configured recommendations for local Ollama models.

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import Any

from Backend.Core.json_io import read_json
from Backend.Core.paths import REPO_ROOT

MODEL_RECOMMENDATIONS_PATH = (
    REPO_ROOT / "Resources" / "ollama-model-recommendations.json"
)


@dataclass(frozen=True)
class OllamaModelTier:
    id: str
    minimum_memory_gb: float
    maximum_memory_gb: float | None
    model: str
    validated_for_full_matrix: bool


@dataclass(frozen=True)
class OllamaModelRecommendations:
    default_model: str
    other_model_warning: str
    tiers: tuple[OllamaModelTier, ...]


@lru_cache(maxsize=1)
def model_recommendations() -> OllamaModelRecommendations:
    payload = read_json(MODEL_RECOMMENDATIONS_PATH)
    return parse_model_recommendations(payload)


def parse_model_recommendations(
    payload: dict[str, Any],
) -> OllamaModelRecommendations:
    version = payload.get("schema_version")
    if type(version) is not int or version != 1:
        raise ValueError("unsupported Ollama model recommendation schema")
    default_model = _required_text(payload, "default_model")
    warning = _required_text(payload, "other_model_warning")
    raw_tiers = payload.get("tiers")
    if not isinstance(raw_tiers, list) or not raw_tiers:
        raise ValueError("Ollama model recommendations require at least one tier")

    tiers: list[OllamaModelTier] = []
    for raw in raw_tiers:
        if not isinstance(raw, dict):
            raise ValueError("each Ollama model tier must be an object")
        minimum = _memory_boundary(raw.get("minimum_memory_gb"), "minimum_memory_gb")
        raw_maximum = raw.get("maximum_memory_gb")
        maximum = (
            _memory_boundary(raw_maximum, "maximum_memory_gb")
            if raw_maximum is not None
            else None
        )
        if minimum < 0:
            raise ValueError("minimum_memory_gb must be non-negative")
        if maximum is not None and maximum <= minimum:
            raise ValueError("maximum_memory_gb must be greater than its minimum")
        qualified = raw.get("validated_for_full_matrix")
        if type(qualified) is not bool:
            raise ValueError("validated_for_full_matrix must be a boolean")
        tiers.append(
            OllamaModelTier(
                id=_required_text(raw, "id"),
                minimum_memory_gb=minimum,
                maximum_memory_gb=maximum,
                model=_required_text(raw, "model"),
                validated_for_full_matrix=qualified,
            )
        )

    tiers.sort(key=lambda tier: tier.minimum_memory_gb)
    if tiers[0].minimum_memory_gb != 0:
        raise ValueError("Ollama model tiers must begin at zero GB")
    for left, right in pairwise(tiers):
        if left.maximum_memory_gb != right.minimum_memory_gb:
            raise ValueError(
                "Ollama model tiers must be contiguous and non-overlapping"
            )
    if tiers[-1].maximum_memory_gb is not None:
        raise ValueError("the final Ollama model tier must have no upper bound")
    if default_model not in {tier.model for tier in tiers}:
        raise ValueError("default_model must appear in an Ollama model tier")
    return OllamaModelRecommendations(
        default_model=default_model,
        other_model_warning=warning,
        tiers=tuple(tiers),
    )


def default_ollama_model() -> str:
    return model_recommendations().default_model


def handle_local_model_guidance(args: Any) -> int:
    """Report current cold-load estimates without downloading or starting a model."""
    import shutil

    from Backend.Core.events import emit
    from Backend.Core.ollama_admission import (
        ResourceAdmissionError,
        _checked_physical_memory,
        _headroom_snapshot,
        local_ollama_cached_sizes,
    )

    try:
        physical = _checked_physical_memory()
        cached_sizes = local_ollama_cached_sizes()
        available = _headroom_snapshot(physical)
        # The app bundle and the default Ollama cache can be on different volumes.
        cache = Path.home() / ".ollama" / "models"
        disk = shutil.disk_usage(
            next(path for path in (cache, *cache.parents) if path.is_dir())
        ).free
    except (ResourceAdmissionError, OSError):
        emit(
            "model_guidance",
            prefer_cloud=True,
            conditions_verified=False,
            recommendations=[],
        )
        return 0
    gib = 1 << 30
    budget = min(available, physical - max(4 * gib, (physical + 3) // 4))
    payload = read_json(MODEL_RECOMMENDATIONS_PATH)
    candidates = [
        (row["model"], math.ceil(row["download_size_gb"] * 10**9))
        for row in reversed(payload["tiers"])
    ]
    rows = []
    for model, download_estimate in candidates:
        cached_size = cached_sizes.get(model)
        size = cached_size if cached_size is not None else download_estimate
        download_bytes = download_estimate if cached_size is None else 0
        required = size + max(2 * gib, (size + 3) // 4)
        rows.append(
            {
                "model": model,
                "estimated_download_bytes": download_bytes,
                "estimated_required_memory_bytes": required,
                "estimated_fit_now": required <= budget
                and (cached_size is not None or download_bytes + gib <= disk),
                "quality_verified": False,
            }
        )
    emit(
        "model_guidance",
        prefer_cloud=True,
        conditions_verified=True,
        physical_memory_bytes=physical,
        available_memory_bytes=available,
        free_disk_bytes=disk,
        recommendations=rows,
    )
    return 0


def _memory_boundary(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        boundary = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not math.isfinite(boundary):
        raise ValueError(f"{name} must be a finite number")
    return boundary


def _required_text(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()
