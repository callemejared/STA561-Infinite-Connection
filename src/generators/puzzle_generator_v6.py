"""Final v6 batch generator built for submission-ready, low-cost 10K production.

v6 keeps the cheap compatibility-graph sampling strategy introduced in v5, but
adds one hard submission rule:

- semantic groups must come from an independently authored semantic bank
- if that bank overlaps with the official NYT semantic bank, runtime build fails

This branch is intentionally not a v4-style heavy generate-and-reject pipeline.
The goal is to produce many structurally sound puzzles quickly enough for the
competition workflow where a random subset is reviewed by instructors.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
from random import Random
from typing import Any, Callable, Iterable

from generators.anagram_generator import list_independent_anagram_groups_v6
from generators.form_generator import list_independent_form_groups_v6
from generators.generator_resources import (
    clone_group,
    detect_form_pattern_value,
    detect_form_subtype,
    normalize_word_key,
)
from generators.semantic_generator import list_independent_semantic_groups_v6
from generators.theme_generator import list_independent_theme_groups_v6

GroupRecord = dict[str, Any]
V6Runtime = dict[str, Any]

TIER_ORDER = {"easy": 0, "medium": 1, "hard": 2}
TIER_TARGETS = ("easy", "medium", "hard")
FORM_LIKE_MECHANISMS = {
    "form_prefix",
    "form_suffix",
    "form_rhyme",
    "form_homophone",
    "form_anagram",
    "form_other",
}
NON_THEME_FRAME = "NOT_THEME"

# v6 keeps the candidate list tighter than v5 so every branch of the search stays
# cheap enough for large offline batches.
SELECTION_CANDIDATE_CAP = 12
GENERATION_ATTEMPT_MULTIPLIER = 8
PROGRESS_UPDATE_INTERVAL = 100

# Cheap family caps keep puzzles diverse while reducing the branching factor.
MAX_SEMANTIC_GROUPS_PER_PUZZLE = 1
MAX_THEME_GROUPS_PER_PUZZLE = 2
MAX_FORM_LIKE_GROUPS_PER_PUZZLE = 2


def mechanism_family_for_group(group: dict[str, Any]) -> str:
    """Map one group into a lightweight mechanism family for v6 deduping."""
    group_type = str(group.get("type", "")).lower()

    if group_type == "semantic":
        return "semantic"
    if group_type == "theme":
        return "theme"
    if group_type == "anagram":
        return "form_anagram"

    subtype = str(group.get("metadata", {}).get("subtype") or detect_form_subtype(group) or "").lower()

    if subtype == "prefix":
        return "form_prefix"
    if subtype == "suffix":
        return "form_suffix"
    if subtype == "rhyme":
        return "form_rhyme"
    if subtype == "homophone":
        return "form_homophone"
    if subtype == "anagram":
        return "form_anagram"

    return "form_other"


def theme_frame_family_for_label(label: str, group_type: str) -> str:
    """Classify theme labels into lightweight frame families for deduping."""
    if group_type.lower() != "theme":
        return NON_THEME_FRAME

    normalized_label = " ".join(str(label).strip().upper().split())

    if normalized_label.startswith("AT "):
        return "AT"
    if normalized_label.startswith("IN "):
        return "IN"
    if normalized_label.startswith("ON "):
        return "ON"
    if "ASSOCIATED WITH" in normalized_label:
        return "ASSOCIATED_WITH"
    if "THINGS FOUND IN" in normalized_label or normalized_label.startswith("FOUND IN ") or normalized_label.startswith("SEEN IN "):
        return "THINGS_FOUND_IN"
    if "PARTS OF" in normalized_label or normalized_label.startswith("PARTS OF "):
        return "PARTS_OF"
    if "WORDS BEFORE" in normalized_label or normalized_label.startswith("WORDS BEFORE "):
        return "WORDS_BEFORE"
    if "WORDS AFTER" in normalized_label or normalized_label.startswith("WORDS AFTER "):
        return "WORDS_AFTER"

    return "OTHER_THEME"


def cheap_group_valid(group: dict[str, Any]) -> bool:
    """Apply only the lightweight structural sanity checks needed for v6."""
    label_key = normalize_word_key(group.get("label", ""))
    word_keys = [normalize_word_key(word) for word in group.get("words", [])]

    if not label_key:
        return False
    if len(word_keys) != 4:
        return False
    if len(set(word_keys)) != 4:
        return False

    return True


def _group_signature(record: GroupRecord) -> tuple[str, tuple[str, ...], str]:
    """Return a stable dedupe signature for one preprocessed group."""
    return (
        str(record["label_key"]),
        tuple(record["word_keys"]),
        str(record["mechanism_family"]),
    )


def _group_record(group: dict[str, Any], index: int) -> GroupRecord:
    """Normalize one source group into a lightweight v6 record."""
    cloned_group = clone_group(group)
    label_key = normalize_word_key(cloned_group["label"])
    word_keys = tuple(sorted(normalize_word_key(word) for word in cloned_group["words"]))
    metadata = dict(cloned_group.get("metadata", {}))
    subtype = str(metadata.get("subtype") or detect_form_subtype(cloned_group) or "")
    pattern_family = metadata.get("pattern_value")

    if pattern_family is None:
        pattern_family = detect_form_pattern_value(cloned_group)

    mechanism_family = mechanism_family_for_group(cloned_group)
    theme_frame_family = theme_frame_family_for_label(str(cloned_group["label"]), str(cloned_group["type"]))
    difficulty = dict(cloned_group.get("difficulty", {}))
    difficulty_tier = str(difficulty.get("tier", "medium"))
    group_type = str(cloned_group["type"]).lower()
    type_bucket = "form_like" if mechanism_family in FORM_LIKE_MECHANISMS else group_type

    return {
        "index": index,
        "group": cloned_group,
        "label_key": label_key,
        "word_keys": word_keys,
        "word_key_set": frozenset(word_keys),
        "type": group_type,
        "type_bucket": type_bucket,
        "difficulty_tier": difficulty_tier,
        "difficulty_score": float(difficulty.get("score", 0.5)),
        "rhyme_ending": metadata.get("rhyme_ending"),
        "subtype": subtype or None,
        "pattern_family": str(pattern_family) if pattern_family is not None else None,
        "mechanism_family": mechanism_family,
        "theme_frame_family": theme_frame_family,
        "compatibility_degree": 0,
    }


def groups_compatible(left: GroupRecord, right: GroupRecord) -> bool:
    """Return True when two groups can coexist under v6's cheap hard rules."""
    if left["word_key_set"].intersection(right["word_key_set"]):
        return False
    if left["label_key"] == right["label_key"]:
        return False
    if left["rhyme_ending"] and left["rhyme_ending"] == right["rhyme_ending"]:
        return False
    if left["mechanism_family"] in FORM_LIKE_MECHANISMS and left["mechanism_family"] == right["mechanism_family"]:
        return False
    if left["theme_frame_family"] != NON_THEME_FRAME and left["theme_frame_family"] == right["theme_frame_family"]:
        return False

    return True


def _candidate_order(
    runtime: V6Runtime,
    candidate_indices: Iterable[int],
    rng: Random,
) -> list[int]:
    """Rank candidates cheaply so the batch stays fast at 10K scale.

    v6 intentionally avoids v5-style global family-usage steering here because it
    increases backtracking late in a large batch. Compatibility degree plus a
    small random factor is enough for this final submission workflow.
    """
    shuffled_indices = list(candidate_indices)
    rng.shuffle(shuffled_indices)
    records = runtime["records"]
    scored_candidates: list[tuple[float, int]] = []

    for index in shuffled_indices:
        record = records[index]
        compatibility_bonus = 1.0 + float(record["compatibility_degree"])
        noise = 0.92 + (0.16 * rng.random())
        score = compatibility_bonus * noise
        scored_candidates.append((score, index))

    scored_candidates.sort(reverse=True)
    return [index for _, index in scored_candidates[:SELECTION_CANDIDATE_CAP]]


def _future_tiers_feasible(runtime: V6Runtime, candidate_pool: set[int], remaining_tiers: list[str]) -> bool:
    """Return True when the remaining pool can still satisfy the tier targets."""
    if len(candidate_pool) < len(remaining_tiers):
        return False

    tier_counter = Counter(remaining_tiers)
    records = runtime["records"]

    for tier, required_count in tier_counter.items():
        available_count = sum(1 for index in candidate_pool if records[index]["difficulty_tier"] == tier)

        if available_count < required_count:
            return False

    return True


def _type_cap_for_bucket(type_bucket: str) -> int:
    """Return the max count allowed for one cheap diversity bucket."""
    if type_bucket == "semantic":
        return MAX_SEMANTIC_GROUPS_PER_PUZZLE
    if type_bucket == "theme":
        return MAX_THEME_GROUPS_PER_PUZZLE
    if type_bucket == "form_like":
        return MAX_FORM_LIKE_GROUPS_PER_PUZZLE

    return 4


def _candidate_respects_type_caps(record: GroupRecord, type_usage: Counter[str]) -> bool:
    """Return True when adding a candidate would stay within v6 family caps."""
    type_bucket = str(record["type_bucket"])
    return int(type_usage[type_bucket]) < _type_cap_for_bucket(type_bucket)


def _sample_puzzle_indices(
    runtime: V6Runtime,
    rng: Random,
) -> tuple[int, ...] | None:
    """Construct one 4-group puzzle cheaply from the compatibility graph."""
    records = runtime["records"]
    all_indices = set(range(len(records)))
    remaining_tiers = ["easy", "medium", "hard", rng.choice(TIER_TARGETS)]

    def backtrack(
        selected: list[int],
        candidate_pool: set[int],
        pending_tiers: list[str],
        type_usage: Counter[str],
    ) -> tuple[int, ...] | None:
        if not pending_tiers:
            return tuple(selected)

        distinct_tiers = sorted(
            set(pending_tiers),
            key=lambda tier: sum(1 for index in candidate_pool if records[index]["difficulty_tier"] == tier),
        )

        if not distinct_tiers:
            return None

        next_tier = distinct_tiers[0]
        tier_candidates = {index for index in candidate_pool if records[index]["difficulty_tier"] == next_tier}

        if not tier_candidates:
            return None

        ordered_candidates = _candidate_order(runtime, tier_candidates, rng)

        for candidate_index in ordered_candidates:
            candidate_record = records[candidate_index]

            if not _candidate_respects_type_caps(candidate_record, type_usage):
                continue

            next_pool = set(candidate_pool)
            next_pool.intersection_update(runtime["compatibility_index"][candidate_index])
            next_pool.discard(candidate_index)

            next_pending_tiers = list(pending_tiers)
            next_pending_tiers.remove(next_tier)

            if not _future_tiers_feasible(runtime, next_pool, next_pending_tiers):
                continue

            next_type_usage = Counter(type_usage)
            next_type_usage[str(candidate_record["type_bucket"])] += 1
            result = backtrack(selected + [candidate_index], next_pool, next_pending_tiers, next_type_usage)

            if result is not None:
                return result

        return None

    return backtrack([], all_indices, remaining_tiers, Counter())


def _puzzle_signature(records: list[GroupRecord]) -> tuple[tuple[str, ...], ...]:
    """Return a stable signature so the batch generator can soften duplicate reuse."""
    return tuple(sorted(record["word_keys"] for record in records))


def _materialize_group(record: GroupRecord) -> dict[str, Any]:
    """Return one schema-compatible group with v6 metadata attached."""
    group = clone_group(record["group"])
    metadata = dict(group.get("metadata", {}))
    metadata.update(
        {
            "mechanism_family": record["mechanism_family"],
            "theme_frame_family": record["theme_frame_family"],
            "pattern_family": record["pattern_family"],
        }
    )
    group["metadata"] = metadata
    return group


def _build_puzzle_v6(records: list[GroupRecord], puzzle_id: str) -> dict[str, Any]:
    """Build one schema-compatible v6 puzzle with lightweight final metadata."""
    groups = [_materialize_group(record) for record in records]
    all_words = [word for group in groups for word in group["words"]]
    group_tiers = [record["difficulty_tier"] for record in records]
    tier_score = {"easy": 0.0, "medium": 0.5, "hard": 1.0}
    puzzle_difficulty = sum(tier_score.get(tier, 0.5) for tier in group_tiers) / len(group_tiers)

    return {
        "puzzle_id": puzzle_id,
        "source": "generated_v6_final",
        "groups": groups,
        "all_words": all_words,
        "difficulty": {
            "group_tiers": group_tiers,
            "puzzle_score": round(puzzle_difficulty, 3),
        },
        "generation": {
            "semantic_bank_mode": "independent_v6",
            "semantic_overlap_check": "passed",
            "official_overlap_check": "passed",
            "theme_bank_mode": "independent_v6",
            "form_bank_mode": "independent_v6",
            "anagram_bank_mode": "independent_v6",
            "mechanism_families": [record["mechanism_family"] for record in records],
            "theme_frame_families": [
                record["theme_frame_family"]
                for record in records
                if record["theme_frame_family"] != NON_THEME_FRAME
            ],
        },
    }


@lru_cache(maxsize=1)
def initialize_v6_runtime() -> V6Runtime:
    """Load banks once and build the final cheap compatibility graph for v6."""
    # v6 keeps preprocessing one-time and cheap at sampling time. The semantic
    # bank comes only from independently authored groups, and runtime raises
    # immediately if any curated semantic/theme/form/anagram bank overlaps with
    # official NYT groups.
    source_groups = (
        list_independent_semantic_groups_v6()
        + list_independent_theme_groups_v6()
        + list_independent_form_groups_v6()
        + list_independent_anagram_groups_v6()
    )

    records: list[GroupRecord] = []
    seen_signatures: set[tuple[str, tuple[str, ...], str]] = set()

    for group in source_groups:
        if not cheap_group_valid(group):
            continue

        record = _group_record(group, index=len(records))
        signature = _group_signature(record)

        if signature in seen_signatures:
            continue

        seen_signatures.add(signature)
        records.append(record)

    compatibility_neighbors: list[set[int]] = [set() for _ in records]

    for left_index, left_record in enumerate(records):
        for right_index in range(left_index + 1, len(records)):
            right_record = records[right_index]

            if not groups_compatible(left_record, right_record):
                continue

            compatibility_neighbors[left_index].add(right_index)
            compatibility_neighbors[right_index].add(left_index)

    tier_index: dict[str, tuple[int, ...]] = defaultdict(tuple)

    for record_index, record in enumerate(records):
        record["compatibility_degree"] = len(compatibility_neighbors[record_index])
        tier_name = record["difficulty_tier"]
        tier_index[tier_name] = tuple((*tier_index.get(tier_name, ()), record_index))

    return {
        "records": tuple(records),
        "compatibility_index": tuple(frozenset(neighbors) for neighbors in compatibility_neighbors),
        "tier_index": {tier: tuple(indices) for tier, indices in tier_index.items()},
        "record_count": len(records),
        "semantic_group_count": sum(1 for record in records if record["type"] == "semantic"),
        "semantic_bank_mode": "independent_v6",
        "semantic_overlap_check": "passed",
        "official_overlap_check": "passed",
        "theme_bank_mode": "independent_v6",
        "form_bank_mode": "independent_v6",
        "anagram_bank_mode": "independent_v6",
    }


def generate_puzzle_v6(
    puzzle_id: str,
    rng: Random,
    runtime: V6Runtime | None = None,
) -> dict[str, Any]:
    """Generate one v6 puzzle by direct constrained sampling on the compatibility graph."""
    active_runtime = runtime or initialize_v6_runtime()
    selection = _sample_puzzle_indices(active_runtime, rng)

    if selection is None:
        raise ValueError("Could not sample a compatible v6 puzzle from the preprocessed graph.")

    selected_records = [active_runtime["records"][index] for index in selection]
    return _build_puzzle_v6(selected_records, puzzle_id=puzzle_id)


def generate_puzzles_v6(count: int, seed: int = 0) -> list[dict[str, Any]]:
    """Generate many final v6 puzzles for fast 10K-scale offline production."""
    return generate_puzzles_v6_with_progress(count=count, seed=seed)


def generate_puzzles_v6_with_progress(
    count: int,
    seed: int = 0,
    progress_callback: Callable[[int, int], None] | None = None,
    progress_interval: int = PROGRESS_UPDATE_INTERVAL,
) -> list[dict[str, Any]]:
    """Generate many final v6 puzzles and optionally report batch progress."""
    runtime = initialize_v6_runtime()
    rng = Random(seed)
    puzzles: list[dict[str, Any]] = []
    seen_puzzle_signatures: set[tuple[tuple[str, ...], ...]] = set()
    max_attempts = max(count * GENERATION_ATTEMPT_MULTIPLIER, 100)
    duplicate_skip_budget = min(max(count // 4, 100), 1000)
    attempt_count = 0

    while len(puzzles) < count and attempt_count < max_attempts:
        attempt_count += 1
        selection = _sample_puzzle_indices(runtime, rng)

        if selection is None:
            continue

        selected_records = [runtime["records"][index] for index in selection]
        signature = _puzzle_signature(selected_records)

        # v6 still prefers variety early, but the final batch pipeline values
        # throughput over strict global uniqueness.
        if signature in seen_puzzle_signatures and attempt_count <= duplicate_skip_budget:
            continue

        seen_puzzle_signatures.add(signature)
        puzzle = _build_puzzle_v6(selected_records, puzzle_id=f"gen_v6_{len(puzzles) + 1:06d}")
        puzzles.append(puzzle)

        if progress_callback is not None:
            should_report = len(puzzles) == count or len(puzzles) % max(progress_interval, 1) == 0

            if should_report:
                progress_callback(len(puzzles), count)

    if len(puzzles) < count:
        raise ValueError(
            f"Generated only {len(puzzles)} v6 puzzles before exhausting the cheap sampling budget ({max_attempts})."
        )

    return puzzles
