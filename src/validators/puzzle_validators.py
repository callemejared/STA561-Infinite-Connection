"""Validators for v1 and v2 Infinite Connections puzzles."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from typing import Any

from validators.duplicate_check import is_duplicate_of_official

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

FORM_LIKE_TYPES = {"FORM", "ANAGRAM"}
VALIDATION_STAGES = (
    "structure",
    "style",
    "ambiguity",
    "duplicate",
    "multi_solution",
    "low_cohesion",
    "high_confusion",
)


@dataclass(frozen=True)
class ValidationConfig:
    """Configurable thresholds for v2 validation."""

    within_group_similarity_threshold: float = 0.18
    cross_group_similarity_threshold: float = 0.16
    max_solution_count: int = 1


def normalize_phrase(text: Any) -> str:
    """Return uppercase text with punctuation collapsed into spaces."""
    letters_only = re.sub(r"[^A-Z0-9]+", " ", str(text).upper())
    return " ".join(letters_only.split())


def normalize_compact(text: Any) -> str:
    """Return uppercase text with spaces and punctuation removed."""
    compact = re.sub(r"[^A-Z0-9]+", "", str(text).upper())
    return compact or normalize_phrase(text).replace(" ", "")


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

        group_type = str(group.get("type", "")).upper()

        if group_type not in FORM_LIKE_TYPES:
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

            if sequence_similarity(left_normalized, right_normalized) >= 0.82:
                reasons.append(f"labels '{left_label}' and '{right_label}' are too similar")

    return dedupe_reasons(reasons)


def sequence_similarity(left: str, right: str) -> float:
    """Compute a lightweight string similarity score."""
    left_bigrams = Counter(left[index : index + 2] for index in range(max(len(left) - 1, 1)))
    right_bigrams = Counter(right[index : index + 2] for index in range(max(len(right) - 1, 1)))
    return cosine_counter_similarity(left_bigrams, right_bigrams)


def estimate_cross_group_confusion(puzzle: dict[str, Any]) -> tuple[int, list[str]]:
    """Score obvious competing surface patterns across different groups."""
    feature_map: dict[str, list[tuple[int, str]]] = defaultdict(list)

    for group_index, group in enumerate(puzzle.get("groups", []), start=1):
        for word in group.get("words", []):
            normalized_word = normalize_compact(word)

            if len(normalized_word) >= 4:
                feature_map[f"prefix2:{normalized_word[:2]}"].append((group_index, str(word)))
            if len(normalized_word) >= 5:
                feature_map[f"prefix3:{normalized_word[:3]}"].append((group_index, str(word)))
                feature_map[f"suffix3:{normalized_word[-3:]}"].append((group_index, str(word)))

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
    """Reject puzzles with obvious alternate surface groupings."""
    reasons: list[str] = []

    for group_index, group in enumerate(puzzle.get("groups", []), start=1):
        if str(group.get("type", "")).upper() in FORM_LIKE_TYPES:
            continue

        normalized_words = [normalize_compact(word) for word in group.get("words", [])]

        if len(normalized_words) == 4 and all(len(word) >= 4 for word in normalized_words):
            prefix2_values = {word[:2] for word in normalized_words}
            suffix3_values = {word[-3:] for word in normalized_words if len(word) >= 5}

            if len(prefix2_values) == 1:
                reasons.append(
                    f"group {group_index} accidentally creates a shared starting pattern outside the intended mechanism"
                )
            if len(suffix3_values) == 1 and suffix3_values:
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


def exact_duplicate_check(
    puzzle: dict[str, Any],
    official_puzzles: list[dict[str, Any]] | None,
) -> bool:
    """Return True when a generated puzzle exactly matches an official one."""
    if official_puzzles is None:
        return False

    return is_duplicate_of_official(puzzle, official_puzzles)


@lru_cache(maxsize=1)
def known_group_lookup() -> dict[tuple[str, ...], list[dict[str, Any]]]:
    """Build a lookup table for all group banks used by the generators."""
    from generators.anagram_generator import list_anagram_groups
    from generators.form_generator import list_form_groups
    from generators.semantic_generator import list_semantic_groups
    from generators.theme_generator import list_theme_groups

    lookup: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    group_sources = (
        list_semantic_groups()
        + list_theme_groups()
        + list_form_groups()
        + list_anagram_groups()
    )

    for group in group_sources:
        key = tuple(sorted(normalize_compact(word) for word in group["words"]))

        if len(key) != 4:
            continue

        lookup[key].append(group)

    return dict(lookup)


@lru_cache(maxsize=1)
def official_word_contexts() -> dict[str, tuple[str, ...]]:
    """Map each official word to the labels it has appeared under."""
    try:
        from data_utils.dataset_loader import load_or_build_dataset_assets
    except Exception:
        return {}

    try:
        official_puzzles, _ = load_or_build_dataset_assets()
    except Exception:
        return {}

    label_map: dict[str, set[str]] = defaultdict(set)

    for puzzle in official_puzzles:
        for group in puzzle.get("groups", []):
            label = str(group.get("label", ""))

            for word in group.get("words", []):
                label_map[normalize_compact(word)].add(label)

    return {
        word_key: tuple(sorted(labels))
        for word_key, labels in label_map.items()
    }


def solve_puzzle_backtracking(
    puzzle: dict[str, Any],
    max_solutions: int = 2,
) -> int:
    """Count how many full 4x4 solutions the current generator banks allow."""
    all_words = list(puzzle.get("all_words", []))

    if len(all_words) != 16:
        return 0

    lookup = known_group_lookup()
    candidate_groups: list[frozenset[int]] = []

    for word_indexes in combinations(range(len(all_words)), 4):
        key = tuple(sorted(normalize_compact(all_words[index]) for index in word_indexes))

        if key in lookup:
            candidate_groups.append(frozenset(word_indexes))

    if not candidate_groups:
        return 0

    groups_by_index: dict[int, list[frozenset[int]]] = defaultdict(list)

    for candidate_group in candidate_groups:
        for word_index in candidate_group:
            groups_by_index[word_index].append(candidate_group)

    @lru_cache(maxsize=None)
    def count_solutions(remaining: tuple[int, ...]) -> int:
        if not remaining:
            return 1

        first_index = remaining[0]
        remaining_set = set(remaining)
        total = 0

        for candidate_group in groups_by_index.get(first_index, []):
            if not candidate_group.issubset(remaining_set):
                continue

            next_remaining = tuple(sorted(remaining_set.difference(candidate_group)))
            total += count_solutions(next_remaining)

            if total > max_solutions:
                return total

        return total

    return count_solutions(tuple(range(len(all_words))))


def load_spacy_model() -> tuple[Any | None, str]:
    """Try to load a lightweight spaCy model, returning None on failure."""
    if hasattr(load_spacy_model, "_cached_value"):
        return getattr(load_spacy_model, "_cached_value")

    try:
        import spacy
    except Exception:
        cached_value = (None, "lexical-fallback")
        setattr(load_spacy_model, "_cached_value", cached_value)
        return cached_value

    for model_name in ("en_core_web_md", "en_core_web_sm"):
        try:
            cached_value = (spacy.load(model_name), model_name)
            setattr(load_spacy_model, "_cached_value", cached_value)
            return cached_value
        except Exception:
            continue

    cached_value = (None, "lexical-fallback")
    setattr(load_spacy_model, "_cached_value", cached_value)
    return cached_value


def lexical_vector(text: str) -> Counter[str]:
    """Build a tiny n-gram vector when a spaCy model is unavailable."""
    features: Counter[str] = Counter()
    normalized = normalize_phrase(text)
    compact = normalize_compact(text)

    for token in normalized.split():
        features[f"token:{token}"] += 1

    for label in official_word_contexts().get(compact, ()):
        features[f"label:{normalize_phrase(label)}"] += 3

        for token in label_tokens(label):
            features[f"label_token:{token}"] += 1

    if len(compact) < 3:
        if compact:
            features[f"gram:{compact}"] += 1
        return features

    for index in range(len(compact) - 2):
        features[f"gram:{compact[index:index + 3]}"] += 1

    return features


def cosine_counter_similarity(left: Counter[str], right: Counter[str]) -> float:
    """Compute cosine similarity for sparse Counter vectors."""
    if not left or not right:
        return 0.0

    dot_product = sum(left[key] * right.get(key, 0) for key in left)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot_product / (left_norm * right_norm)


def cosine_dense_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity for dense numeric vectors."""
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot_product / (left_norm * right_norm)


@lru_cache(maxsize=4096)
def vectorize_text(text: str) -> tuple[str, Counter[str] | list[float]]:
    """Vectorize one word or phrase using spaCy if available."""
    nlp, backend_name = load_spacy_model()

    if nlp is None:
        return backend_name, lexical_vector(text)

    document = nlp(text)
    vector = [float(value) for value in document.vector]

    if not vector or math.isclose(sum(value * value for value in vector), 0.0):
        return "lexical-fallback", lexical_vector(text)

    return backend_name, vector


@lru_cache(maxsize=8192)
def pairwise_similarity(left: str, right: str) -> tuple[str, float]:
    """Return the backend name and cosine similarity for one pair of words."""
    left_backend, left_vector = vectorize_text(left)
    right_backend, right_vector = vectorize_text(right)

    if isinstance(left_vector, Counter) or isinstance(right_vector, Counter):
        left_counter = left_vector if isinstance(left_vector, Counter) else lexical_vector(left)
        right_counter = right_vector if isinstance(right_vector, Counter) else lexical_vector(right)
        return "lexical-fallback", cosine_counter_similarity(left_counter, right_counter)

    backend_name = left_backend if left_backend == right_backend else "mixed"
    return backend_name, cosine_dense_similarity(left_vector, right_vector)


def embedding_score(puzzle: dict[str, Any]) -> dict[str, Any]:
    """Measure within-group cohesion and cross-group confusion."""
    within_group_scores: list[float] = []
    cross_group_scores: list[float] = []
    backend_names: Counter[str] = Counter()
    groups = list(puzzle.get("groups", []))

    for group in groups:
        for left_word, right_word in combinations(group.get("words", []), 2):
            backend_name, similarity = pairwise_similarity(str(left_word), str(right_word))
            backend_names.update([backend_name])
            within_group_scores.append(similarity)

    for left_index, left_group in enumerate(groups):
        for right_group in groups[left_index + 1 :]:
            for left_word in left_group.get("words", []):
                for right_word in right_group.get("words", []):
                    backend_name, similarity = pairwise_similarity(str(left_word), str(right_word))
                    backend_names.update([backend_name])
                    cross_group_scores.append(similarity)

    average_within = sum(within_group_scores) / len(within_group_scores) if within_group_scores else 0.0
    average_cross = sum(cross_group_scores) / len(cross_group_scores) if cross_group_scores else 0.0

    return {
        "backend": backend_names.most_common(1)[0][0] if backend_names else "unknown",
        "average_within_group_similarity": average_within,
        "average_cross_group_similarity": average_cross,
        "within_pair_count": len(within_group_scores),
        "cross_pair_count": len(cross_group_scores),
    }


def validate_puzzle(
    puzzle: dict[str, Any],
    official_puzzles: list[dict[str, Any]] | None = None,
    config: ValidationConfig | None = None,
) -> dict[str, Any]:
    """Run the full v2 validation stack and return detailed results."""
    validation_config = config or ValidationConfig()
    structure_reasons = validate_structure(puzzle)
    style_reasons = validate_style(puzzle)
    ambiguity_reasons = validate_ambiguity_and_overlap(puzzle)

    duplicate_reasons: list[str] = []
    if official_puzzles is not None and exact_duplicate_check(puzzle, official_puzzles):
        duplicate_reasons.append("puzzle exactly matches an official puzzle")

    solution_count = solve_puzzle_backtracking(
        puzzle,
        max_solutions=validation_config.max_solution_count + 1,
    )
    multi_solution_reasons = []

    if solution_count > validation_config.max_solution_count:
        multi_solution_reasons.append(f"solver found {solution_count} valid solutions")

    similarity_metrics = embedding_score(puzzle)
    low_cohesion_reasons = []
    high_confusion_reasons = []

    if similarity_metrics["average_within_group_similarity"] < validation_config.within_group_similarity_threshold:
        low_cohesion_reasons.append(
            "average within-group similarity "
            f"({similarity_metrics['average_within_group_similarity']:.3f}) is below the threshold "
            f"({validation_config.within_group_similarity_threshold:.3f})"
        )

    if similarity_metrics["average_cross_group_similarity"] > validation_config.cross_group_similarity_threshold:
        high_confusion_reasons.append(
            "average cross-group similarity "
            f"({similarity_metrics['average_cross_group_similarity']:.3f}) is above the threshold "
            f"({validation_config.cross_group_similarity_threshold:.3f})"
        )

    reason_groups = {
        "structure": structure_reasons,
        "style": style_reasons,
        "ambiguity": ambiguity_reasons,
        "duplicate": duplicate_reasons,
        "multi_solution": multi_solution_reasons,
        "low_cohesion": low_cohesion_reasons,
        "high_confusion": high_confusion_reasons,
    }

    return {
        "is_valid": not any(reason_groups.values()),
        "reason_groups": reason_groups,
        "metrics": {
            "solution_count": solution_count,
            **similarity_metrics,
        },
    }


def first_failure_stage(validation_result: dict[str, Any]) -> str | None:
    """Return the first validation stage that failed."""
    reason_groups = validation_result.get("reason_groups", {})

    for stage in VALIDATION_STAGES:
        if reason_groups.get(stage):
            return stage

    return None


def collect_validation_report(puzzle: dict[str, Any]) -> dict[str, list[str]]:
    """Preserve the lightweight v1 report format."""
    return {
        "structure": validate_structure(puzzle),
        "style": validate_style(puzzle),
        "ambiguity": validate_ambiguity_and_overlap(puzzle),
    }
