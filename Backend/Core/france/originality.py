# Conservative French NSI similarity screen with labelled-fixture thresholds.

import re
from difflib import SequenceMatcher

CALIBRATION_SET_ID = "fr-nsi-labelled-v1"
THRESHOLDS = {
    "contiguous_characters": 160,
    "prose_five_gram_jaccard": 0.45,
    "prose_sequence_ratio": 0.78,
    "normalised_code_four_gram_jaccard": 0.70,
}
COMMON_INSTRUCTIONS = (
    "justifier la réponse",
    "répondre aux questions suivantes",
    "on considère",
    "à partir des documents",
)
CODE_BLOCK = re.compile(r"```(?:python|sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


# The candidate exceeded a calibrated similarity threshold.
class SimilarityRejected(ValueError):
    pass


def _normalise_prose(value: str) -> tuple[str, list[str]]:
    value = CODE_BLOCK.sub(" ", value.casefold())
    for phrase in COMMON_INSTRUCTIONS:
        value = value.replace(phrase, " ")
    tokens = re.findall(r"[^\W_]+", value)
    return " ".join(tokens), tokens


def _normalise_code(value: str) -> list[str]:
    blocks = CODE_BLOCK.findall(value)
    tokens: list[str] = []
    keywords = {
        "and",
        "as",
        "def",
        "else",
        "elif",
        "false",
        "for",
        "from",
        "if",
        "in",
        "is",
        "none",
        "not",
        "or",
        "return",
        "select",
        "true",
        "where",
        "while",
    }
    for block in blocks:
        for token in re.findall(
            r"[A-Za-zÀ-ÿ_][\wÀ-ÿ]*|\d+|==|!=|<=|>=|[-+*/%<>()\[\],:]", block.casefold()
        ):
            if re.fullmatch(r"[A-Za-zÀ-ÿ_][\wÀ-ÿ]*", token) and token not in keywords:
                tokens.append("IDENTIFIER")
            else:
                tokens.append(token)
    return tokens


def _shingles(tokens: list[str], width: int) -> set[tuple[str, ...]]:
    if len(tokens) < width:
        return set()
    return {
        tuple(tokens[index : index + width]) for index in range(len(tokens) - width + 1)
    }


def _jaccard(left: set, right: set) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _longest_common_substring(left: str, right: str) -> int:
    """Return the exact contiguous match length, indexing the shorter text."""
    if not left or not right:
        return 0
    if len(left) > len(right):
        left, right = right, left

    # Each suffix-automaton state stores outgoing characters, its longest
    # represented substring length, and a link to the next shorter suffix.
    transitions: list[dict[str, int]] = [{}]
    lengths = [0]
    links = [-1]
    last = 0
    for character in left:
        end = len(transitions)
        transitions.append({})
        lengths.append(lengths[last] + 1)
        links.append(0)
        state = last
        while state >= 0 and character not in transitions[state]:
            transitions[state][character] = end
            state = links[state]
        if state >= 0:
            target = transitions[state][character]
            if lengths[state] + 1 == lengths[target]:
                links[end] = target
            else:
                # Split off the shorter suffix without changing its continuations.
                clone = len(transitions)
                transitions.append(transitions[target].copy())
                lengths.append(lengths[state] + 1)
                links.append(links[target])
                while state >= 0 and transitions[state].get(character) == target:
                    transitions[state][character] = clone
                    state = links[state]
                links[target] = links[end] = clone
        last = end

    state = length = longest = 0
    for character in right:
        while state and character not in transitions[state]:
            state = links[state]
            length = lengths[state]
        target = transitions[state].get(character)
        if target is None:
            state = length = 0
        else:
            state = target
            length += 1
            longest = max(longest, length)
    return longest


def _scores(candidate: str, comparison: str) -> dict[str, float | int]:
    candidate_prose, candidate_tokens = _normalise_prose(candidate)
    comparison_prose, comparison_tokens = _normalise_prose(comparison)
    longest = _longest_common_substring(candidate_prose, comparison_prose)
    prose_jaccard = _jaccard(
        _shingles(candidate_tokens, 5), _shingles(comparison_tokens, 5)
    )
    sequence_ratio = (
        SequenceMatcher(
            None, candidate_tokens, comparison_tokens, autojunk=False
        ).ratio()
        if min(len(candidate_tokens), len(comparison_tokens)) >= 20
        else 0.0
    )
    code_jaccard = _jaccard(
        _shingles(_normalise_code(candidate), 4),
        _shingles(_normalise_code(comparison), 4),
    )
    return {
        "contiguous_characters": longest,
        "prose_five_gram_jaccard": round(prose_jaccard, 6),
        "prose_sequence_ratio": round(sequence_ratio, 6),
        "normalised_code_four_gram_jaccard": round(code_jaccard, 6),
    }


def _too_similar(scores: dict[str, float | int]) -> bool:
    return any(scores[name] >= threshold for name, threshold in THRESHOLDS.items())


def screen_originality(
    candidate_text: str,
    reference_texts: list[str],
    *,
    previous_texts: list[str] | None = None,
) -> dict:
    if not isinstance(candidate_text, str) or len(candidate_text.strip()) < 40:
        raise ValueError("Texte candidat insuffisant pour le contrôle d'originalité")
    comparisons = [
        ("référence", value) for value in reference_texts if isinstance(value, str)
    ]
    comparisons.extend(
        ("génération précédente", value)
        for value in (previous_texts or [])
        if isinstance(value, str)
    )
    maximums: dict[str, float | int] = {name: 0 for name in THRESHOLDS}
    for source_kind, comparison in comparisons:
        scores = _scores(candidate_text, comparison)
        for name, score in scores.items():
            maximums[name] = max(maximums[name], score)
        if _too_similar(scores):
            raise SimilarityRejected(
                f"Contrôle d'originalité refusé : proximité avec une {source_kind}"
            )
    return {
        "state": "passed_calibrated_screen",
        "calibration_set": CALIBRATION_SET_ID,
        "thresholds": dict(THRESHOLDS),
        "maximum_scores": maximums,
        "comparison_counts": {
            "references": len(reference_texts),
            "previous_generations": len(previous_texts or []),
        },
        "copyright_guarantee": False,
        "teacher_review_required": True,
    }
