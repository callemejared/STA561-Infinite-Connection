"""Runtime helpers for live-generated Infinite Connections v5 puzzles."""

from __future__ import annotations

from collections import Counter
from random import Random
from time import perf_counter
from typing import Any

from batch_generate_and_score import load_official_dataset_assets
from generators.form_generator import list_form_groups
from generators.puzzle_assembler import generate_candidate_puzzle_v4
from generators.semantic_generator import list_semantic_groups
from generators.similarity_tools import load_embedding_backend
from generators.theme_generator import list_theme_groups
from validators.duplicate_check import canonicalize_puzzle
from validators.puzzle_validators import ValidationConfig, first_failure_stage, known_group_lookup, validate_puzzle

# Keep one button click from triggering an overly long blocking search in Streamlit live generation.
DEFAULT_LIVE_ATTEMPT_BUDGET = 6


def initialize_v4_runtime() -> dict[str, Any]:
    """Warm the heavy resources needed for live v5 generation exactly once."""
    warmup: dict[str, float | int | str] = {}
    total_start = perf_counter()

    bank_start = perf_counter()
    semantic_groups = list_semantic_groups()
    theme_groups = list_theme_groups()
    form_groups = list_form_groups()
    warmup["group_bank_seconds"] = round(perf_counter() - bank_start, 2)
    warmup["semantic_group_count"] = len(semantic_groups)
    warmup["theme_group_count"] = len(theme_groups)
    warmup["form_group_count"] = len(form_groups)

    dataset_start = perf_counter()
    official_puzzles, dataset_stats = load_official_dataset_assets()
    warmup["official_dataset_seconds"] = round(perf_counter() - dataset_start, 2)
    warmup["official_puzzle_count"] = len(official_puzzles)
    warmup["official_word_pool_size"] = len(dataset_stats.get("word_pool", []))

    embedding_start = perf_counter()
    embedding_backend, _ = load_embedding_backend()
    warmup["embedding_seconds"] = round(perf_counter() - embedding_start, 2)
    warmup["embedding_backend"] = embedding_backend

    lookup_start = perf_counter()
    lookup = known_group_lookup()
    warmup["lookup_seconds"] = round(perf_counter() - lookup_start, 2)
    warmup["lookup_key_count"] = len(lookup)

    warmup["total_seconds"] = round(perf_counter() - total_start, 2)

    return {
        "official_puzzles": official_puzzles,
        "validation_config": ValidationConfig(),
        "warmup": warmup,
    }


def generate_validated_live_puzzle(
    runtime: dict[str, Any],
    seed: int,
    puzzle_index: int,
    seen_puzzle_keys: set[tuple[tuple[str, ...], ...]] | None = None,
    max_candidates: int = DEFAULT_LIVE_ATTEMPT_BUDGET,
) -> dict[str, Any]:
    """Generate and validate one fresh v5 puzzle using warmed resources."""
    rng = Random(seed)
    rejection_counts: Counter[str] = Counter()
    seen_keys = seen_puzzle_keys or set()
    total_start = perf_counter()

    for candidate_index in range(1, max_candidates + 1):
        puzzle_id = f"live_v5_{puzzle_index:06d}_{candidate_index:02d}"

        try:
            candidate_puzzle = generate_candidate_puzzle_v4(
                puzzle_id=puzzle_id,
                rng=rng,
                seed=seed,
            )
        except ValueError:
            rejection_counts["generation_error"] += 1
            continue

        validation_result = validate_puzzle(
            candidate_puzzle,
            official_puzzles=runtime["official_puzzles"],
            config=runtime["validation_config"],
        )
        failed_stage = first_failure_stage(validation_result)

        if failed_stage is not None:
            rejection_counts[failed_stage] += 1
            continue

        puzzle_key = canonicalize_puzzle(candidate_puzzle)

        if puzzle_key in seen_keys:
            rejection_counts["repeat"] += 1
            continue

        elapsed_seconds = round(perf_counter() - total_start, 2)

        return {
            "puzzle": candidate_puzzle,
            "validation_result": validation_result,
            "stats": {
                "elapsed_seconds": elapsed_seconds,
                "candidate_attempts": candidate_index,
                "rejection_counts": dict(rejection_counts),
                "validation_backend": validation_result["metrics"]["backend"],
                "solution_count": validation_result["metrics"]["solution_count"],
            },
        }

    raise ValueError(
        f"Could not generate a fully validated v5 puzzle within {max_candidates} live attempts. "
        "Try again with a new seed or raise the attempt budget."
    )
