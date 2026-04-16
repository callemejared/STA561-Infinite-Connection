"""Lightweight validators for generated Connections-style puzzles."""

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

GENERIC_LABELS = {
    "ADJECTIVE",
    "ADJECTIVES",
    "CATEGORY",
    "CATEGORIES",
    "NAME",
    "NAMES",
    "NOUN",
    "NOUNS",
    "STUFF",
    "THING",
    "THINGS",
    "VERB",
    "VERBS",
    "WORD",
    "WORDS",
}

GENERIC_LABEL_PATTERNS = [
    re.compile(r"^\d+\s*LETTER\s+WORDS?$"),
    re.compile(r"^\d+\s*[- ]\s*LETTER\s+WORDS?$"),
]

STOPWORDS = {
    "A",
    "AN",
    "AND",
    "AT",
    "FOR",
    "IN",
    "OF",
    "ON",
    "THE",
    "TO",
    "WITH",
}


def normalize_phrase(text: Any) -> str:
    """Return uppercase text with punctuation collapsed into spaces."""
    letters_only = re.sub(r"[^A-Z0-9]+", " ", str(text).upper())
    return " ".join(letters_only.split())


def normalize_compact(text: Any) -> str:
    """Return uppercase text with spaces and punctuation removed."""
    return re.sub(r"[^A-Z0-9]+", "", str(text).upper())


def singularize(token: str) -> str:
    """Apply a tiny singularization heuristic for label comparisons."""
    if token.endswith("IES") and len(token) > 3:
        return f"{token[:-3]}Y"
    if token.endswith("S") and not token.endswith("SS") and len(token) > 3:
        return token[:-1]
    return token


def label_tokens(label: str) -> list[str]:
    """Return the content words inside a label."""
    tokens = []

    for token in normalize_phrase(label).split():
        if token in STOPWORDS:
            continue
        tokens.append(singularize(token))

    return tokens


def dedupe_reasons(reasons: list[str]) -> list[str]:
    """Keep the first copy of each reason while preserving order."""
    seen: set[str] = set()
    unique_reasons = []

    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        unique_reasons.append(reason)

    return unique_reasons


def describe_surface_feature(feature_key: str) -> str:
    """Turn a feature key into a short human-readable description."""
    feature_type, feature_value = feature_key.split(":", maxsplit=1)

    if feature_type == "prefix2":
        return f"start with '{feature_value}'"
    if feature_type == "prefix3":
        return f"start with '{feature_value}'"
    return f"end with '{feature_value}'"


def flatten_group_words(puzzle: dict[str, Any]) -> list[str]:
    """Return the word list implied by the stored groups."""
    flattened_words = []

    for group in puzzle.get("groups", []):
        flattened_words.extend(group.get("words", []))

    return flattened_words


def validate_structure(puzzle: dict[str, Any]) -> list[str]:
    """Check the required 4x4 puzzle structure."""
    reasons: list[str] = []
    groups = puzzle.get("groups", [])

    if len(groups) != 4:
        reasons.append("puzzle must contain exactly 4 groups")

    flattened_words = flatten_group_words(puzzle)

    for group_index, group in enumerate(groups, start=1):
        if len(group.get("words", [])) != 4:
            reasons.append(f"group {group_index} must contain exactly 4 words")

    if len(flattened_words) != 16:
        reasons.append("puzzle must contain exactly 16 group words in total")

    normalized_group_words = [normalize_compact(word) for word in flattened_words]

    if len(normalized_group_words) != len(set(normalized_group_words)):
        reasons.append("each word must be used exactly once across the four groups")

    all_words = puzzle.get("all_words", [])

    if len(all_words) != 16:
        reasons.append("all_words must contain exactly 16 entries")
    if list(all_words) != flattened_words:
        reasons.append("all_words must match the flattened group words in order")

    normalized_all_words = [normalize_compact(word) for word in all_words]

    if len(normalized_all_words) != len(set(normalized_all_words)):
        reasons.append("all_words must not repeat words")

    return dedupe_reasons(reasons)


def validate_style(puzzle: dict[str, Any]) -> list[str]:
    """Reject labels that are overly generic or too revealing."""
    reasons: list[str] = []
    groups = puzzle.get("groups", [])

    for group_index, group in enumerate(groups, start=1):
        label = str(group.get("label", "")).strip()
        normalized_label = normalize_phrase(label)

        if not normalized_label:
            reasons.append(f"group {group_index} is missing a label")
            continue

        if normalized_label in GENERIC_LABELS:
            reasons.append(f"group {group_index} label '{label}' is too generic")

        for pattern in GENERIC_LABEL_PATTERNS:
            if pattern.fullmatch(normalized_label):
                reasons.append(f"group {group_index} label '{label}' is too generic")
                break

        if group.get("type") != "form":
            revealing_tokens = [token for token in label_tokens(label) if len(token) >= 4]

            for word in group.get("words", []):
                normalized_word = normalize_compact(word)
                if any(token == normalized_word or token in normalized_word for token in revealing_tokens):
                    reasons.append(
                        f"group {group_index} label '{label}' is too revealing because it appears in '{word}'"
                    )
                    break

    labels = [str(group.get("label", "")).strip() for group in groups]

    for left_index in range(len(labels)):
        for right_index in range(left_index + 1, len(labels)):
            left_label = labels[left_index]
            right_label = labels[right_index]
            left_normalized = normalize_phrase(left_label)
            right_normalized = normalize_phrase(right_label)

            if not left_normalized or not right_normalized:
                continue

            if left_normalized == right_normalized:
                reasons.append(f"labels '{left_label}' and '{right_label}' are repeated")
                continue

            if left_normalized in right_normalized or right_normalized in left_normalized:
                reasons.append(f"labels '{left_label}' and '{right_label}' are too similar")
                continue

            left_tokens = set(label_tokens(left_label))
            right_tokens = set(label_tokens(right_label))

            if left_tokens and right_tokens and left_tokens == right_tokens:
                reasons.append(f"labels '{left_label}' and '{right_label}' are too similar")
                continue

            similarity = SequenceMatcher(None, left_normalized, right_normalized).ratio()

            if similarity >= 0.82:
                reasons.append(f"labels '{left_label}' and '{right_label}' are too similar")

    return dedupe_reasons(reasons)


def estimate_cross_group_confusion(puzzle: dict[str, Any]) -> tuple[int, list[str]]:
    """Score obvious competing surface patterns across different groups."""
    feature_map: dict[str, list[tuple[int, str]]] = defaultdict(list)

    for group_index, group in enumerate(puzzle.get("groups", []), start=1):
        for word in group.get("words", []):
            normalized_word = normalize_compact(word)

            if len(normalized_word) >= 4:
                feature_map[f"prefix2:{normalized_word[:2]}"].append((group_index, word))
            if len(normalized_word) >= 5:
                feature_map[f"prefix3:{normalized_word[:3]}"].append((group_index, word))
                feature_map[f"suffix3:{normalized_word[-3:]}"].append((group_index, word))

    score = 0
    notes: list[str] = []

    for feature_key, matches in feature_map.items():
        groups_hit = {group_index for group_index, _ in matches}

        if len(groups_hit) < 3:
            continue

        if len(matches) >= 4:
            score += 2
            notes.append(
                f"words from multiple groups all {describe_surface_feature(feature_key)}, "
                "which suggests an alternate grouping"
            )
        elif len(matches) == 3:
            score += 1

    return score, dedupe_reasons(notes)


def validate_ambiguity_and_overlap(puzzle: dict[str, Any]) -> list[str]:
    """Reject puzzles with obvious alternate surface groupings.

    This is intentionally lightweight. We are not solving the whole puzzle here.
    Instead, we block puzzles that accidentally create strong prefix/suffix patterns
    across multiple groups, because those are a common source of bad ambiguity.
    """

    reasons: list[str] = []

    for group_index, group in enumerate(puzzle.get("groups", []), start=1):
        if group.get("type") == "form":
            continue

        normalized_words = [normalize_compact(word) for word in group.get("words", [])]

        if len(normalized_words) == 4 and all(len(word) >= 4 for word in normalized_words):
            prefix2_values = {word[:2] for word in normalized_words}
            suffix3_values = {word[-3:] for word in normalized_words if len(word) >= 5}

            if len(prefix2_values) == 1:
                reasons.append(
                    f"group {group_index} accidentally creates a shared starting pattern outside the intended mechanism"
                )
            if len(suffix3_values) == 1 and len(suffix3_values) != 0:
                reasons.append(
                    f"group {group_index} accidentally creates a shared ending pattern outside the intended mechanism"
                )

    confusion_score, confusion_notes = estimate_cross_group_confusion(puzzle)

    if confusion_score >= 2:
        reasons.append(
            f"cross-group confusion score is {confusion_score}, which suggests an alternate grouping is too visible"
        )
        reasons.extend(confusion_notes[:2])

    return dedupe_reasons(reasons)


def collect_validation_report(puzzle: dict[str, Any]) -> dict[str, list[str]]:
    """Run the three lightweight validator groups and return their reasons."""
    return {
        "structure": validate_structure(puzzle),
        "style": validate_style(puzzle),
        "ambiguity": validate_ambiguity_and_overlap(puzzle),
    }
