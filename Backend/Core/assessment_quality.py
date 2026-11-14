# Check item data and compare completed papers for repeated content.

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from Backend.Core.assessment_contracts import AssessmentContract


NUMBER_PATTERN = re.compile(
    r"(?<![\w.])[£$€]?[+-]?\d+(?:[,.]\d+)*(?:\s?(?:%|000|m|bn))?",
    flags=re.IGNORECASE,
)
WORD_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


# Return a stable comparison form without conflating visible output text.
def normalise_item_text(value: str, *, abstract_numbers: bool = True) -> str:

    text = unicodedata.normalize("NFKC", value).casefold()
    if abstract_numbers:
        text = NUMBER_PATTERN.sub(" <number> ", text)
    return " ".join(WORD_PATTERN.findall(text))


# Extract quantities exactly enough to catch broken data/source rewrites.
def numeric_tokens(value: str) -> tuple[str, ...]:

    return tuple(
        " ".join(match.group(0).casefold().split())
        for match in NUMBER_PATTERN.finditer(value)
    )


# Validate candidate quantities against their declared semantic roles.
def validate_candidate_contract(
    original: str,
    candidate: str,
    contract: AssessmentContract,
    generated_values: Mapping[str, float] | None = None,
) -> None:

    original_precision = _precision_instructions(original)
    candidate_precision = _precision_instructions(candidate)
    if original_precision != candidate_precision:
        raise ValueError(
            f"{contract.item_id} changed the required precision instruction"
        )

    expected_values = [
        value
        for value in contract.numeric_values
        if value.role.value == "assessment_data"
    ]
    expected = Counter(_normalise_quantity(value.text) for value in expected_values)
    actual_tokens = list(numeric_tokens(candidate))

    label_roles = {"code_line_label", "item_identifier", "display_label"}
    declared_labels = {
        _normalise_quantity(value.text)
        for value in contract.numeric_values
        if value.role.value in label_roles
    }
    leading_label_lines = frozenset(
        index
        for index, line in enumerate(original.splitlines())
        if (match := re.match(r"\s*(\d{1,3})(?=\s+\S)", line))
        and _normalise_quantity(match.group(1)) in declared_labels
    )
    ignored = _ignored_candidate_quantities(
        candidate, leading_label_lines=leading_label_lines
    )
    ignored.extend(_precision_digit_tokens(candidate))
    _subtract_tokens(actual_tokens, ignored)

    supplied = generated_values or {}
    declared_fields = {field.name: field for field in contract.generated_numeric_fields}
    unknown_fields = set(supplied) - set(declared_fields)
    if unknown_fields:
        raise ValueError(
            f"{contract.item_id} supplied undeclared generated numeric fields: "
            f"{sorted(unknown_fields)}"
        )
    for name, value in supplied.items():
        declared_fields[name].validate_value(float(value))
        _subtract_tokens(actual_tokens, _value_tokens(value))

    actual = Counter(_normalise_quantity(token) for token in actual_tokens)
    numeric_values_match = (
        not (expected - actual)
        if contract.allow_additional_numeric_values
        else actual == expected
    )
    if not numeric_values_match:
        raise ValueError(
            f"{contract.item_id} changed immutable numeric data: "
            f"expected {expected}, got {actual}"
        )

    ordered = [
        _normalise_quantity(value.text) for value in expected_values if value.ordered
    ]
    if ordered and not _is_subsequence(
        ordered,
        [_normalise_quantity(token) for token in actual_tokens],
    ):
        raise ValueError(f"{contract.item_id} changed ordered immutable numeric data")


# Reject common exchange-rate reversals before model review.
def validate_economics_causal_direction(value: str) -> None:

    text = " ".join(value.casefold().split())
    import_cost = r"(?:import (?:costs?|prices?)|(?:costs?|prices?) of imports)"
    higher = r"(?:raises?|increases?|higher|more expensive)"
    lower = r"(?:lowers?|reduces?|decreases?|lower|cheaper)"
    reversed_relationships = (
        rf"\bappreciat\w*\b.{{0,100}}{higher}.{{0,50}}{import_cost}",
        rf"\bdepreciat\w*\b.{{0,100}}{lower}.{{0,50}}{import_cost}",
    )
    if any(re.search(pattern, text) for pattern in reversed_relationships):
        raise ValueError("economics item has a reversed exchange-rate direction")


def _normalise_quantity(value: str) -> str:
    return " ".join(value.casefold().split())


def _ignored_candidate_quantities(
    value: str, *, leading_label_lines: frozenset[int] = frozenset()
) -> list[str]:
    ignored: list[str] = []
    patterns = (
        r"\[\s*(\d+)\s+marks?\s*\]",
        r"\b(?:question|extract|figure|table)\s+(\d+)\b",
        r"\bline\s+(\d+)\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, value, flags=re.IGNORECASE):
            ignored.extend(numeric_tokens(match.group(0)))
    for index, line in enumerate(value.splitlines()):
        if index in leading_label_lines and (
            match := re.match(r"\s*(\d{1,3})(?=\s+\S)", line)
        ):
            ignored.append(match.group(1))
    return ignored


def _precision_instructions(value: str) -> tuple[tuple[int, str], ...]:
    words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
    }
    pattern = re.compile(
        r"\b(one|two|three|four|five|\d+)\s+"
        r"(decimal\s+places?|significant\s+figures?)\b",
        flags=re.IGNORECASE,
    )
    return tuple(
        (
            (
                words[match.group(1).casefold()]
                if match.group(1).casefold() in words
                else int(match.group(1))
            ),
            "decimal"
            if match.group(2).casefold().startswith("decimal")
            else "significant",
        )
        for match in pattern.finditer(value)
    )


def _precision_digit_tokens(value: str) -> list[str]:
    return [
        match.group(1)
        for match in re.finditer(
            r"\b(\d+)\s+(?:decimal\s+places?|significant\s+figures?)\b",
            value,
            flags=re.IGNORECASE,
        )
    ]


def _value_tokens(value: float) -> list[str]:
    return [format(float(value), "g")]


def _subtract_tokens(tokens: list[str], values: Iterable[str]) -> None:
    for value in values:
        normalised = _normalise_quantity(value)
        for index, token in enumerate(tokens):
            if _normalise_quantity(token) == normalised:
                tokens.pop(index)
                break


def _is_subsequence(expected: list[str], actual: list[str]) -> bool:
    iterator = iter(actual)
    return all(any(candidate == value for candidate in iterator) for value in expected)


def item_fingerprint(value: str) -> str:
    normalised = normalise_item_text(value)
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


# Weighted token-shingle Jaccard similarity in the closed interval 0...1.
def content_similarity(left: str, right: str, *, width: int = 3) -> float:
    return _shingle_similarity(
        _shingles(normalise_item_text(left), width=width),
        _shingles(normalise_item_text(right), width=width),
    )


def _shingle_similarity(
    left: Counter[tuple[str, ...]], right: Counter[tuple[str, ...]]
) -> float:
    if not left or not right:
        return 0.0 if left or right else 1.0
    if len(left) > len(right):
        left, right = right, left
    intersection = sum(min(count, right[key]) for key, count in left.items())
    union = left.total() + right.total() - intersection
    return intersection / union if union else 0.0


def assert_distinct_items(
    items: Iterable[dict[str, Any]],
    *,
    threshold: float = 0.84,
    context: str = "paper",
) -> None:
    _checked_item_shingles(list(items), threshold=threshold, context=context)


class ItemSimilarityIndex:
    """Admit a paper's items without rechecking pairs it has already accepted."""

    def __init__(self, *, threshold: float, context: str) -> None:
        self.threshold = threshold
        self.context = context
        self._accepted: dict[str, tuple[str, Counter[tuple[str, ...]]]] = {}

    def admit(self, prompts: Mapping[str, str]) -> None:
        changed = {
            item_id: prompt.strip()
            for item_id, prompt in prompts.items()
            if item_id not in self._accepted
            or prompt.strip() != self._accepted[item_id][0]
        }
        if not changed:
            return
        if self._accepted.keys() & changed.keys():
            # A replacement can introduce a conflict with a later item. Check
            # the whole updated set in its original order before replacing it.
            all_prompts = {
                item_id: prompt for item_id, (prompt, _) in self._accepted.items()
            } | changed
            checked = _checked_item_shingles(
                [
                    {"id": item_id, "prompt": prompt}
                    for item_id, prompt in all_prompts.items()
                ],
                threshold=self.threshold,
                context=self.context,
            )
            self._accepted = {
                item["id"]: (item["prompt"], shingles) for item, shingles in checked
            }
            return

        pending: dict[str, tuple[str, Counter[tuple[str, ...]]]] = {}
        for item_id, prompt in changed.items():
            if not prompt:
                raise ValueError(f"{self.context} item {item_id} has no prompt")
            shingles = _shingles(normalise_item_text(prompt), width=3)
            for previous in (self._accepted, pending):
                for previous_id, (_, previous_shingles) in previous.items():
                    _check_similarity(
                        previous_id,
                        item_id,
                        previous_shingles,
                        shingles,
                        threshold=self.threshold,
                        context=self.context,
                    )
            pending[item_id] = (prompt, shingles)
        # A failed batch never changes the admitted set.
        self._accepted.update(pending)


def _check_similarity(
    previous_id: object,
    item_id: object,
    previous_shingles: Counter[tuple[str, ...]],
    shingles: Counter[tuple[str, ...]],
    *,
    threshold: float,
    context: str,
) -> None:
    score = _shingle_similarity(shingles, previous_shingles)
    if score >= threshold:
        raise ValueError(
            f"{context} items {previous_id} and {item_id} are too similar ({score:.3f})"
        )


def _checked_item_shingles(
    items: Sequence[dict[str, Any]], *, threshold: float, context: str
) -> list[tuple[dict[str, Any], Counter[tuple[str, ...]]]]:
    checked: list[tuple[dict[str, Any], Counter[tuple[str, ...]]]] = []
    for index, item in enumerate(items):
        prompt = str(item.get("prompt", "")).strip()
        if not prompt:
            raise ValueError(f"{context} item {item.get('id', index)} has no prompt")
        shingles = _shingles(normalise_item_text(prompt), width=3)
        for previous, previous_shingles in checked:
            _check_similarity(
                previous.get("id"),
                item.get("id"),
                previous_shingles,
                shingles,
                threshold=threshold,
                context=context,
            )
        checked.append((item, shingles))
    return checked


# Compare a completed assessment package with earlier published packages.
def validate_package_novelty(
    package_path: Path,
    *,
    history_root: Path,
    threshold: float = 0.84,
    cross_generation_policy: str = "strict-cross-generation-v1",
) -> dict[str, Any]:
    if cross_generation_policy not in (
        "strict-cross-generation-v1",
        "repeat-practice-v1",
    ):
        raise ValueError("Unknown cross-generation similarity policy")
    strict_history = cross_generation_policy == "strict-cross-generation-v1"
    current = _load_package(package_path)
    current_items = _checked_item_shingles(
        _items(current), threshold=threshold, context="paper"
    )

    comparisons = 0
    skipped_history_packages = 0
    historical_overlap = False
    nearest: dict[str, Any] | None = None
    current_path = package_path.resolve()
    for historic_path in sorted(history_root.glob("*-assessment.json")):
        if (
            historic_path.name == package_path.name
            or historic_path.resolve() == current_path
        ):
            continue
        try:
            historic = _load_package(historic_path)
            historic_items = _normalised_historical_items(historic)
        except (OSError, ValueError):
            skipped_history_packages += 1
            continue
        # Retain shingles for the current paper and at most this historical
        # package. Preserve pair order for nearest matches and strict refusals.
        historic_shingles: dict[int, Counter[tuple[str, ...]]] = {}
        for item, shingles in current_items:
            for index, (historic_item, prompt) in enumerate(historic_items):
                if item.get("subject") != historic_item.get("subject") or item.get(
                    "paper"
                ) != historic_item.get("paper"):
                    continue
                comparisons += 1
                if index not in historic_shingles:
                    historic_shingles[index] = _shingles(prompt, width=3)
                score = _shingle_similarity(shingles, historic_shingles[index])
                if nearest is None or score > float(nearest["similarity"]):
                    nearest = {
                        "similarity": round(score, 4),
                        "current_item": item.get("id"),
                        "historic_item": historic_item.get("id"),
                        "historic_package": historic_path.name,
                    }
                if score >= threshold:
                    historical_overlap = True
                    if strict_history:
                        raise ValueError(
                            f"generated item {item.get('id')} is too similar to "
                            f"{historic_path.name}:{historic_item.get('id')} "
                            f"({score:.3f}); choose a new seed or regenerate"
                        )
    return {
        "algorithm": "weighted-token-shingle-jaccard-v1",
        "threshold": threshold,
        "historic_comparisons": comparisons,
        "nearest_match": nearest,
        # Neither permitted overlap nor unreadable history proves originality.
        "passed": False
        if historical_overlap
        else (None if skipped_history_packages else True),
        "history_complete": skipped_history_packages == 0,
        "skipped_history_packages": skipped_history_packages,
        "cross_generation_policy": cross_generation_policy,
        "within_paper_passed": True,
        "historical_overlap": historical_overlap,
    }


def _shingles(value: str, *, width: int) -> Counter[tuple[str, ...]]:
    words = value.split()
    if not words:
        return Counter()
    actual_width = min(width, len(words))
    return Counter(
        tuple(words[index : index + actual_width])
        for index in range(len(words) - actual_width + 1)
    )


def _load_package(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError(f"unsupported assessment package: {path}")
    return raw


def _items(package: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = package.get("items", [])
    if not isinstance(raw_items, list):
        raise ValueError("assessment package items must be a list")
    return [item for item in raw_items if isinstance(item, dict)]


def _normalised_historical_items(
    package: dict[str, Any],
) -> list[tuple[dict[str, Any], str]]:
    """Require usable comparison records, without claiming full package approval."""
    raw_items = package.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("historical assessment items must be a nonempty list")
    items = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("historical assessment contains an invalid item")
        for field in ("id", "subject", "paper", "prompt"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    "historical assessment item has invalid comparison data"
                )
            if field != "prompt" and any(character.isspace() for character in value):
                raise ValueError("historical assessment item has invalid metadata")
        prompt = normalise_item_text(item["prompt"])
        if not prompt:
            raise ValueError("historical assessment item has no comparison text")
        items.append((item, prompt))
    return items
