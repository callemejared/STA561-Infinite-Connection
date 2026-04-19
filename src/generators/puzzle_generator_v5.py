"""Low-cost v5 batch generator built for high-throughput offline puzzle production.

v5 reuses the existing v4 group banks, tiers, metadata, schema, and normalization
helpers, but intentionally removes v4's heavy per-puzzle search/validation loop.

The batch-generation use case here is different from v4:
- v4 optimizes hard for one puzzle at a time and can afford expensive rejection.
- v5 optimizes for producing many structurally sound puzzles quickly.

For the 10K-game competition workflow, the class/instructor sample a subset for
manual review, so the generator should prefer throughput, type variety, and basic
structural sanity over expensive uniqueness/confusion guarantees.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
from random import Random
from typing import Any, Callable, Iterable

from generators.anagram_generator import list_anagram_groups
from generators.form_generator import list_form_groups
from generators.generator_resources import (
    clone_group,
    detect_form_pattern_value,
    detect_form_subtype,
    normalize_word_key,
)
from generators.semantic_generator import list_semantic_groups
from generators.theme_generator import list_theme_groups

GroupRecord = dict[str, Any]
V5Runtime = dict[str, Any]

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
SELECTION_CANDIDATE_CAP = 18
GENERATION_ATTEMPT_MULTIPLIER = 12
PROGRESS_UPDATE_INTERVAL = 100


def mechanism_family_for_group(group: dict[str, Any]) -> str:
    """Map one group into a cheap mechanism family for v5 diversity control."""
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
    """Apply only lightweight structural sanity checks suitable for batch mode."""
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
    """Return a dedupe signature that keeps one copy of equivalent group options."""
    return (
        str(record["label_key"]),
        tuple(record["word_keys"]),
        str(record["mechanism_family"]),
    )


def _group_record(group: dict[str, Any], index: int) -> GroupRecord:
    """Normalize one source group into a lightweight v5 record."""
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

    return {
        "index": index,
        "group": cloned_group,
        "label_key": label_key,
        "word_keys": word_keys,
        "word_key_set": frozenset(word_keys),
        "type": str(cloned_group["type"]),
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
    """Return True when two groups can coexist under v5's cheap hard constraints."""
    if left["word_key_set"].intersection(right["word_key_set"]):
        return False
    if left["label_key"] == right["label_key"]:
        return False

    if left["rhyme_ending"] and left["rhyme_ending"] == right["rhyme_ending"]:
        return False

    if left["mechanism_family"] in FORM_LIKE_MECHANISMS and left["mechanism_family"] == right["mechanism_family"]:
        return False

    if (
        left["theme_frame_family"] != NON_THEME_FRAME
        and left["theme_frame_family"] == right["theme_frame_family"]
    ):
        return False

    return True


def _candidate_order(
    runtime: V5Runtime,
    candidate_indices: Iterable[int],
    rng: Random,
    mechanism_usage: Counter[str],
    theme_frame_usage: Counter[str],
) -> list[int]:
    """Rank candidates cheaply to keep the 10K batch varied without heavy scoring."""
    shuffled_indices = list(candidate_indices)
    rng.shuffle(shuffled_indices)
    records = runtime["records"]
    scored_candidates: list[tuple[float, int]] = []

    for index in shuffled_indices:
        record = records[index]
        family_penalty = 1.0 + float(mechanism_usage[record["mechanism_family"]])
        frame_penalty = 1.0 + float(theme_frame_usage[record["theme_frame_family"]])
        compatibility_bonus = 1.0 + float(record["compatibility_degree"])
        noise = 0.9 + (0.2 * rng.random())
        score = (compatibility_bonus * noise) / (family_penalty * frame_penalty)
        scored_candidates.append((score, index))

    scored_candidates.sort(reverse=True)
    return [index for _, index in scored_candidates[:SELECTION_CANDIDATE_CAP]]


def _future_tiers_feasible(runtime: V5Runtime, candidate_pool: set[int], remaining_tiers: list[str]) -> bool:
    """Cheap feasibility check so v5 avoids walking into dead branches."""
    if len(candidate_pool) < len(remaining_tiers):
        return False

    tier_counter = Counter(remaining_tiers)
    records = runtime["records"]

    for tier, required_count in tier_counter.items():
        available_count = sum(1 for index in candidate_pool if records[index]["difficulty_tier"] == tier)

        if available_count < required_count:
            return False

    return True


def _sample_puzzle_indices(
    runtime: V5Runtime,
    rng: Random,
    mechanism_usage: Counter[str],
    theme_frame_usage: Counter[str],
) -> tuple[int, ...] | None:
    """Construct one 4-group puzzle cheaply from the compatibility graph."""
    records = runtime["records"]
    all_indices = set(range(len(records)))
    remaining_tiers = ["easy", "medium", "hard", rng.choice(TIER_TARGETS)]

    def backtrack(selected: list[int], candidate_pool: set[int], pending_tiers: list[str]) -> tuple[int, ...] | None:
        if not pending_tiers:
            return tuple(selected)

        distinct_tiers = sorted(set(pending_tiers), key=lambda tier: sum(1 for index in candidate_pool if records[index]["difficulty_tier"] == tier))

        if not distinct_tiers:
            return None

        next_tier = distinct_tiers[0]
        tier_candidates = {index for index in candidate_pool if records[index]["difficulty_tier"] == next_tier}

        if not tier_candidates:
            return None

        ordered_candidates = _candidate_order(runtime, tier_candidates, rng, mechanism_usage, theme_frame_usage)

        for candidate_index in ordered_candidates:
            next_pool = set(candidate_pool)
            next_pool.intersection_update(runtime["compatibility_index"][candidate_index])
            next_pool.discard(candidate_index)
            next_pending_tiers = list(pending_tiers)
            next_pending_tiers.remove(next_tier)

            if not _future_tiers_feasible(runtime, next_pool, next_pending_tiers):
                continue

            result = backtrack(selected + [candidate_index], next_pool, next_pending_tiers)

            if result is not None:
                return result

        return None

    return backtrack([], all_indices, remaining_tiers)


def _puzzle_signature(records: list[GroupRecord]) -> tuple[tuple[str, ...], ...]:
    """Return a stable signature so the batch generator can avoid duplicate puzzles."""
    return tuple(sorted(record["word_keys"] for record in records))


def _materialize_group(record: GroupRecord) -> dict[str, Any]:
    """Return one schema-compatible group with cheap v5 metadata attached."""
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


def _build_puzzle_v5(records: list[GroupRecord], puzzle_id: str) -> dict[str, Any]:
    """Build one schema-compatible v5 puzzle with only cheap summary metadata."""
    groups = [_materialize_group(record) for record in records]
    all_words = [word for group in groups for word in group["words"]]
    group_tiers = [record["difficulty_tier"] for record in records]
    tier_score = {"easy": 0.0, "medium": 0.5, "hard": 1.0}
    puzzle_difficulty = sum(tier_score.get(tier, 0.5) for tier in group_tiers) / len(group_tiers)

    return {
        "puzzle_id": puzzle_id,
        "source": "generated_v5",
        "groups": groups,
        "all_words": all_words,
        "difficulty": {
            "group_tiers": group_tiers,
            "puzzle_score": round(puzzle_difficulty, 3),
        },
        "generation": {
            "mechanism_families": [record["mechanism_family"] for record in records],
            "theme_frame_families": [
                record["theme_frame_family"]
                for record in records
                if record["theme_frame_family"] != NON_THEME_FRAME
            ],
        },
    }


@lru_cache(maxsize=1)
def initialize_v5_runtime() -> V5Runtime:
    """Load banks once and build the cheap compatibility graph for v5."""
    # v5 intentionally keeps preprocessing offline and one-time so the batch loop
    # stays cheap. We reuse the v4 banks/tier metadata but do not reuse v4's
    # heavy per-puzzle analysis/validation path.
    source_groups = (
        list_semantic_groups()
        + list_theme_groups()
        + list_form_groups()
        + list_anagram_groups()
    )

    records: list[GroupRecord] = []
    seen_signatures: set[tuple[str, tuple[str, ...], str]] = set()

    for source_index, group in enumerate(source_groups):
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
    }


def generate_puzzle_v5(
    puzzle_id: str,
    rng: Random,
    mechanism_usage: Counter[str] | None = None,
    theme_frame_usage: Counter[str] | None = None,
    runtime: V5Runtime | None = None,
) -> dict[str, Any]:
    """Generate one v5 puzzle by direct constrained sampling on the compatibility graph."""
    active_runtime = runtime or initialize_v5_runtime()
    family_usage = mechanism_usage or Counter()
    frame_usage = theme_frame_usage or Counter()
    selection = _sample_puzzle_indices(active_runtime, rng, family_usage, frame_usage)

    if selection is None:
        raise ValueError("Could not sample a compatible v5 puzzle from the preprocessed graph.")

    selected_records = [active_runtime["records"][index] for index in selection]
    return _build_puzzle_v5(selected_records, puzzle_id=puzzle_id)


def generate_puzzles_v5(count: int, seed: int = 0) -> list[dict[str, Any]]:
    """Generate many low-cost v5 puzzles for high-throughput offline review."""
    return generate_puzzles_v5_with_progress(count=count, seed=seed)


def generate_puzzles_v5_with_progress(
    count: int,
    seed: int = 0,
    progress_callback: Callable[[int, int], None] | None = None,
    progress_interval: int = PROGRESS_UPDATE_INTERVAL,
) -> list[dict[str, Any]]:
    """Generate many low-cost v5 puzzles and optionally report batch progress.

    The callback is intentionally lightweight so Streamlit or CLI callers can show
    progress without changing the cheap v5 sampling loop into a heavy live pipeline.
    """
    runtime = initialize_v5_runtime()
    rng = Random(seed)
    puzzles: list[dict[str, Any]] = []
    mechanism_usage: Counter[str] = Counter()
    theme_frame_usage: Counter[str] = Counter()
    seen_puzzle_signatures: set[tuple[tuple[str, ...], ...]] = set()
    max_attempts = max(count * GENERATION_ATTEMPT_MULTIPLIER, 100)
    duplicate_skip_budget = max(count * 2, 100)
    attempt_count = 0

    while len(puzzles) < count and attempt_count < max_attempts:
        attempt_count += 1
        selection = _sample_puzzle_indices(runtime, rng, mechanism_usage, theme_frame_usage)

        if selection is None:
            continue

        selected_records = [runtime["records"][index] for index in selection]
        signature = _puzzle_signature(selected_records)

        # v5 is optimized for throughput, so duplicate avoidance is only a soft
        # preference. We skip repeats early in the run to improve variety, then
        # allow them later instead of stalling the 10K batch on uniqueness.
        if signature in seen_puzzle_signatures and attempt_count <= duplicate_skip_budget:
            continue

        seen_puzzle_signatures.add(signature)
        puzzle = _build_puzzle_v5(selected_records, puzzle_id=f"gen_v5_{len(puzzles) + 1:06d}")
        puzzles.append(puzzle)
        mechanism_usage.update(record["mechanism_family"] for record in selected_records)
        theme_frame_usage.update(
            record["theme_frame_family"]
            for record in selected_records
            if record["theme_frame_family"] != NON_THEME_FRAME
        )

        if progress_callback is not None:
            should_report = len(puzzles) == count or len(puzzles) % max(progress_interval, 1) == 0

            if should_report:
                progress_callback(len(puzzles), count)

    if len(puzzles) < count:
        raise ValueError(
            f"Generated only {len(puzzles)} v5 puzzles before exhausting the cheap sampling budget ({max_attempts})."
        )

    return puzzles
