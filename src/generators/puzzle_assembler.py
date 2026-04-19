"""Helpers for assembling full 16-word v4 puzzles from scored group banks."""

from __future__ import annotations

from random import Random
from typing import Any

from generators.form_generator import list_form_groups
from generators.puzzle_analysis import (
    MIN_INTERFERENCE_SCORE,
    analyze_puzzle_groups,
    cross_word_link_score,
    pattern_match_score,
    word_group_affinity,
)
from generators.semantic_generator import list_semantic_groups
from generators.theme_generator import list_theme_groups
from generators.generator_resources import clone_group, normalize_word_key

V4_MECHANISM_PLANS = [
    ["semantic", "theme", "form", "semantic"],
    ["semantic", "theme", "form", "theme"],
    ["semantic", "theme", "form", "form"],
]

GROUP_LISTERS = {
    "semantic": list_semantic_groups,
    "theme": list_theme_groups,
    "form": list_form_groups,
}

def normalize_word(word: str) -> str:
    """Return a comparison-friendly word key."""
    return normalize_word_key(word)


def build_puzzle(
    groups: list[dict[str, object]],
    puzzle_id: str,
    source: str = "generated_v4",
    seed: int | None = None,
    analysis: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Build a puzzle object in the shared internal schema."""
    copied_groups = [clone_group(group) for group in groups]
    all_words = [word for group in copied_groups for word in group["words"]]
    puzzle: dict[str, Any] = {
        "puzzle_id": puzzle_id,
        "source": source,
        "groups": copied_groups,
        "all_words": all_words,
    }

    if seed is not None:
        puzzle["seed"] = seed

    if analysis is not None:
        puzzle["difficulty"] = {
            "group_scores": [round(float(score), 3) for score in analysis["effective_scores"]],
            "group_tiers": list(analysis["base_tiers"]),
            "effective_tiers": list(analysis["effective_tiers"]),
            "puzzle_score": round(float(analysis["puzzle_difficulty"]), 3),
        }
        puzzle["analysis"] = {
            "interference_score": round(float(analysis["interference_score"]), 3),
            "decoy_group_count": int(analysis["decoy_group_count"]),
            "pair_details": analysis["pair_details"],
            "group_decoys": analysis["group_decoys"],
        }

    return puzzle


def _compatible_group(
    group: dict[str, Any],
    used_words: set[str],
    used_labels: set[str],
    used_rhyme_endings: set[str],
) -> bool:
    """Return True when a group can be added to the current puzzle."""
    group_words = {normalize_word(str(word)) for word in group["words"]}
    label_key = normalize_word(str(group["label"]))
    rhyme_ending = group.get("metadata", {}).get("rhyme_ending")

    if len(group_words) != 4:
        return False
    if used_words.intersection(group_words):
        return False
    if label_key in used_labels:
        return False
    if rhyme_ending and rhyme_ending in used_rhyme_endings:
        return False

    return True


def _pair_interference_score(left_group: dict[str, Any], right_group: dict[str, Any]) -> float:
    """Estimate how much two groups can distract a solver from each other."""
    left_hits = sorted(
        (
            max(word_group_affinity(str(left_word), right_group), pattern_match_score(str(left_word), right_group))
            for left_word in left_group["words"]
        ),
        reverse=True,
    )
    right_hits = sorted(
        (
            max(word_group_affinity(str(right_word), left_group), pattern_match_score(str(right_word), left_group))
            for right_word in right_group["words"]
        ),
        reverse=True,
    )
    cross_links = sorted(
        (
            max(0.0, cross_word_link_score(str(left_word), str(right_word)) - 0.12)
            for left_word in left_group["words"]
            for right_word in right_group["words"]
        ),
        reverse=True,
    )

    return sum(left_hits[:2]) + sum(right_hits[:2]) + (0.4 * sum(cross_links[:4]))


def _pair_ambiguity_risk(left_group: dict[str, Any], right_group: dict[str, Any]) -> float:
    """Estimate when two groups are drifting from decoy-rich to unfairly ambiguous."""
    risk = 0.0

    for left_word in left_group["words"]:
        own_affinity = word_group_affinity(str(left_word), left_group)
        other_affinity = word_group_affinity(str(left_word), right_group)

        if other_affinity > own_affinity + 0.08:
            risk += other_affinity - own_affinity

    for right_word in right_group["words"]:
        own_affinity = word_group_affinity(str(right_word), right_group)
        other_affinity = word_group_affinity(str(right_word), left_group)

        if other_affinity > own_affinity + 0.08:
            risk += other_affinity - own_affinity

    return risk


def _score_candidate_addition(candidate: dict[str, Any], selected_groups: list[dict[str, Any]], rng: Random) -> float:
    """Score how well one candidate increases cross-group interference."""
    base_score = float(candidate["difficulty"]["score"])

    if not selected_groups:
        return base_score + (0.05 * rng.random())

    interference_score = sum(_pair_interference_score(candidate, selected_group) for selected_group in selected_groups)
    ambiguity_penalty = sum(_pair_ambiguity_risk(candidate, selected_group) for selected_group in selected_groups)
    return interference_score - (1.15 * ambiguity_penalty) + (0.2 * base_score) + (0.05 * rng.random())


def _weighted_pick(rng: Random, scored_candidates: list[tuple[float, dict[str, Any]]]) -> dict[str, Any]:
    """Choose from the strongest candidates with deterministic weighted randomness."""
    scored_candidates = sorted(scored_candidates, key=lambda item: item[0], reverse=True)
    trimmed_candidates = scored_candidates[: max(1, min(20, len(scored_candidates)))]
    minimum_score = trimmed_candidates[-1][0]
    adjusted_weights = [max(score - minimum_score + 0.05, 0.05) for score, _ in trimmed_candidates]
    cutoff = rng.random() * sum(adjusted_weights)
    running_total = 0.0

    for weight, (_, candidate) in zip(adjusted_weights, trimmed_candidates):
        running_total += weight

        if cutoff <= running_total:
            return clone_group(candidate)

    return clone_group(trimmed_candidates[-1][1])


def _choose_group(
    mechanism: str,
    required_tier: str | None,
    rng: Random,
    selected_groups: list[dict[str, Any]],
    used_words: set[str],
    used_labels: set[str],
    used_rhyme_endings: set[str],
) -> dict[str, Any]:
    """Choose one v4 group while prioritizing interference-rich combinations."""
    candidates = []

    for group in GROUP_LISTERS[mechanism]():
        if required_tier is not None and group["difficulty"]["tier"] != required_tier:
            continue
        if not _compatible_group(group, used_words, used_labels, used_rhyme_endings):
            continue

        candidates.append(group)

    if not candidates:
        raise ValueError(f"Could not find an available {mechanism} group for tier {required_tier!r}.")

    scored_candidates = [(_score_candidate_addition(group, selected_groups, rng), group) for group in candidates]
    return _weighted_pick(rng, scored_candidates)


def generate_candidate_puzzle_v4(
    puzzle_id: str,
    seed: int | None = None,
    rng: Random | None = None,
    mechanism_plan: list[str] | None = None,
    max_attempts: int = 300,
) -> dict[str, object]:
    """Generate one v4 candidate puzzle with tier coverage and decoy constraints."""
    local_rng = rng if rng is not None else Random(seed)

    for _ in range(max_attempts):
        plan = list(mechanism_plan) if mechanism_plan is not None else list(local_rng.choice(V4_MECHANISM_PLANS))
        required_tiers = ["easy", "medium", "hard", None]
        local_rng.shuffle(required_tiers)
        groups: list[dict[str, Any]] = []
        used_words: set[str] = set()
        used_labels: set[str] = set()
        used_rhyme_endings: set[str] = set()

        for mechanism, required_tier in zip(plan, required_tiers):
            try:
                group = _choose_group(
                    mechanism=mechanism,
                    required_tier=required_tier,
                    rng=local_rng,
                    selected_groups=groups,
                    used_words=used_words,
                    used_labels=used_labels,
                    used_rhyme_endings=used_rhyme_endings,
                )
            except ValueError:
                groups = []
                break

            groups.append(group)
            used_words.update(normalize_word(str(word)) for word in group["words"])
            used_labels.add(normalize_word(str(group["label"])))

            rhyme_ending = group.get("metadata", {}).get("rhyme_ending")
            if rhyme_ending:
                used_rhyme_endings.add(str(rhyme_ending))

        if len(groups) != 4:
            continue

        local_rng.shuffle(groups)
        analysis = analyze_puzzle_groups([clone_group(group) for group in groups])

        if not analysis["covers_all_tiers"]:
            continue
        if not analysis["difficulty_in_range"]:
            continue
        if analysis["decoy_group_count"] < 4:
            continue
        if analysis["ambiguous_words"]:
            continue
        if analysis["outside_form_matches"]:
            continue
        if analysis["singleton_words"]:
            continue
        if analysis["interference_score"] < MIN_INTERFERENCE_SCORE:
            continue

        return build_puzzle(groups, puzzle_id=puzzle_id, seed=seed, analysis=analysis)

    raise ValueError("Could not assemble a v4 puzzle from the current generator banks.")


def generate_candidate_puzzles_v4(
    count: int,
    seed: int = 0,
    start_index: int = 1,
) -> list[dict[str, object]]:
    """Generate many v4 candidate puzzles with deterministic sampling."""
    rng = Random(seed)
    puzzles = []

    for offset in range(count):
        puzzle_id = f"gen_v4_{start_index + offset:06d}"
        puzzles.append(generate_candidate_puzzle_v4(puzzle_id=puzzle_id, rng=rng, seed=seed))

    return puzzles


def generate_candidate_puzzle_v2(*args: Any, **kwargs: Any) -> dict[str, object]:
    """Compatibility wrapper for older imports."""
    return generate_candidate_puzzle_v4(*args, **kwargs)


def generate_candidate_puzzles_v2(*args: Any, **kwargs: Any) -> list[dict[str, object]]:
    """Compatibility wrapper for older imports."""
    return generate_candidate_puzzles_v4(*args, **kwargs)
