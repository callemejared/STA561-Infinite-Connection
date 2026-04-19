"""Shared puzzle-analysis helpers for v4 assembly and validation."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any

from generators.generator_resources import normalize_word_key, pronunciation_list, rhyme_ending
from generators.similarity_tools import text_similarity

DECOY_SIMILARITY_THRESHOLD = 0.24
THEME_DISTRACTIBILITY_THRESHOLD = 0.24
SINGLETON_LINK_THRESHOLD = 0.18
AMBIGUITY_MARGIN = 0.10
PUZZLE_DIFFICULTY_RANGE = (0.35, 0.68)
MIN_INTERFERENCE_SCORE = 2.25


def pattern_match_score(word: str, group: dict[str, Any]) -> float:
    """Return a lightweight score when a word matches a form group's pattern."""
    metadata = group.get("metadata", {})
    subtype = metadata.get("subtype")
    pattern_value = metadata.get("pattern_value")
    normalized_word = normalize_word_key(word)

    if subtype == "prefix" and pattern_value and normalized_word.startswith(str(pattern_value)):
        return 0.62
    if subtype == "suffix" and pattern_value and normalized_word.endswith(str(pattern_value)):
        return 0.62
    if subtype == "rhyme" and metadata.get("rhyme_ending") and rhyme_ending(word) == metadata["rhyme_ending"]:
        return 0.60
    if subtype == "homophone" and pattern_value and str(pattern_value) in pronunciation_list(word):
        return 0.60
    if subtype == "anagram" and pattern_value and "".join(sorted(normalized_word)) == str(pattern_value):
        return 0.60

    return 0.0


def word_group_affinity(word: str, group: dict[str, Any]) -> float:
    """Score how strongly one word points toward a group's label or form pattern."""
    _, label_similarity = text_similarity(word, str(group["label"]))
    return max(label_similarity, pattern_match_score(word, group))


def cross_word_link_score(left_word: str, right_word: str) -> float:
    """Measure how much two words from different groups could be linked by a solver."""
    _, similarity = text_similarity(left_word, right_word)
    return similarity


def theme_distractibility_in_puzzle(group_index: int, groups: list[dict[str, Any]]) -> int:
    """Count how many outside words point toward a theme group label."""
    group = groups[group_index]

    if str(group["type"]) != "theme":
        return 0

    outside_words = [
        str(word)
        for other_index, other_group in enumerate(groups)
        if other_index != group_index
        for word in other_group["words"]
    ]

    return sum(1 for word in outside_words if word_group_affinity(word, group) >= THEME_DISTRACTIBILITY_THRESHOLD)


def analyze_puzzle_groups(groups: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute v4 difficulty, decoy, ambiguity, and singleton metrics."""
    effective_scores: list[float] = []
    base_tiers: list[str] = []
    effective_tiers: list[str] = []
    group_decoys: list[list[dict[str, Any]]] = []
    ambiguous_words: list[dict[str, Any]] = []
    singleton_words: list[dict[str, Any]] = []
    pair_overlap_counts: dict[tuple[int, int], int] = defaultdict(int)
    pair_overlap_scores: dict[tuple[int, int], float] = defaultdict(float)

    for group_index, group in enumerate(groups):
        base_score = float(group.get("difficulty", {}).get("score", 0.5))
        base_tiers.append(str(group.get("difficulty", {}).get("tier", "medium")))

        if str(group["type"]) == "theme":
            distractibility_count = theme_distractibility_in_puzzle(group_index, groups)
            distractibility_score = distractibility_count / 12.0
            effective_score = (base_score + distractibility_score) / 2.0
        else:
            distractibility_count = 0
            effective_score = base_score

        group_decoy_hits: list[dict[str, Any]] = []
        effective_scores.append(effective_score)
        effective_tiers.append("easy" if effective_score < 0.34 else "medium" if effective_score < 0.67 else "hard")

        for word in group["words"]:
            own_affinity = word_group_affinity(str(word), group)
            best_other_affinity = 0.0
            best_other_label = None
            best_link = 0.0

            for other_index, other_group in enumerate(groups):
                if other_index == group_index:
                    continue

                competing_affinity = word_group_affinity(str(word), other_group)

                if competing_affinity >= DECOY_SIMILARITY_THRESHOLD:
                    group_decoy_hits.append(
                        {
                            "word": str(word),
                            "competing_label": str(other_group["label"]),
                            "score": round(competing_affinity, 3),
                        }
                    )
                    pair_key = tuple(sorted((group_index, other_index)))
                    pair_overlap_counts[pair_key] += 1
                    pair_overlap_scores[pair_key] += competing_affinity

                if competing_affinity > best_other_affinity:
                    best_other_affinity = competing_affinity
                    best_other_label = str(other_group["label"])

                for other_word in other_group["words"]:
                    best_link = max(best_link, cross_word_link_score(str(word), str(other_word)), pattern_match_score(str(word), other_group))

            if best_other_affinity > own_affinity + AMBIGUITY_MARGIN:
                ambiguous_words.append(
                    {
                        "word": str(word),
                        "own_label": str(group["label"]),
                        "competing_label": best_other_label,
                        "own_score": round(own_affinity, 3),
                        "competing_score": round(best_other_affinity, 3),
                    }
                )

            if best_link < SINGLETON_LINK_THRESHOLD:
                singleton_words.append(
                    {
                        "word": str(word),
                        "group_label": str(group["label"]),
                        "best_link_score": round(best_link, 3),
                    }
                )

        group_decoys.append(group_decoy_hits)
        group.setdefault("analysis", {})
        group["analysis"]["puzzle_theme_distractibility"] = distractibility_count
        group["analysis"]["effective_difficulty"] = effective_score

    pair_details = []

    for left_index, right_index in combinations(range(len(groups)), 2):
        pair_key = (left_index, right_index)
        pair_details.append(
            {
                "left_label": str(groups[left_index]["label"]),
                "right_label": str(groups[right_index]["label"]),
                "overlap_count": pair_overlap_counts.get(pair_key, 0),
                "overlap_score": round(pair_overlap_scores.get(pair_key, 0.0), 3),
            }
        )

    puzzle_difficulty = sum(effective_scores) / len(effective_scores) if effective_scores else 0.0

    return {
        "effective_scores": effective_scores,
        "base_tiers": base_tiers,
        "effective_tiers": effective_tiers,
        "group_decoys": group_decoys,
        "ambiguous_words": ambiguous_words,
        "singleton_words": singleton_words,
        "pair_details": pair_details,
        "interference_score": sum(pair_overlap_scores.values()),
        "decoy_group_count": sum(1 for decoys in group_decoys if decoys),
        "puzzle_difficulty": puzzle_difficulty,
        "difficulty_in_range": PUZZLE_DIFFICULTY_RANGE[0] <= puzzle_difficulty <= PUZZLE_DIFFICULTY_RANGE[1],
        "covers_all_tiers": {"easy", "medium", "hard"}.issubset(set(base_tiers)),
    }
